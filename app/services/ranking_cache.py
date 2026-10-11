"""Private production-only vector and pagination storage; never stores source text.

Single deployment/shared local disk contract. Atomic replacement supports readers
in other workers; exclusive leases suppress duplicate lifecycle generations.
Snapshots are opaque, authorization-bound, ten-minute traversal views.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from contextlib import contextmanager

import httpx

from app.core.config import settings
from app.embeddings.factory import get_embedding_provider
from app.embeddings.profile import embedding_profile, profile_fingerprint
from app.services.matching_fingerprint import fingerprint_cv, fingerprint_job
from app.services.matching_text_privacy import MATCHING_CANONICAL_VERSION, find_matching_text_privacy_issues
from app.services.semantic_matching_service import cosine_similarity


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def runtime_identity():
    return {
        "profile": profile_fingerprint(embedding_profile(settings.embedding_provider,
            settings.embedding_model, settings.embedding_num_ctx, settings.embedding_num_batch)),
        "model_digest": settings.ranking_model_digest,
        "canonical_version": MATCHING_CANONICAL_VERSION,
        "engine": "semantic-v1",
    }


def entity_identity(kind, canonical):
    return {**runtime_identity(), "kind": kind,
            "fingerprint": fingerprint_cv(canonical) if kind == "cv" else fingerprint_job(canonical),
            "text_sha256": hashlib.sha256(canonical.semantic_text.encode()).hexdigest()}


class RankingCache:
    def __init__(self, root=None):
        self.root = Path(root or settings.ranking_cache_root)

    def _path(self, area, key):
        # Keys are generated hashes/UUIDs, never caller paths.
        if not key or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Invalid private cache key")
        return self.root / area / (key + ".json")

    def read(self, area, key):
        try:
            return json.loads(self._path(area, key).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def write(self, area, key, payload):
        path = self._path(area, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(payload, stream, allow_nan=False, separators=(",", ":"))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @contextmanager
    def lease(self, key):
        path = self._path("leases", key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # No takeover: a crashed task leaves PENDING until operator removes
            # its verified lease. Never risk duplicate provider calls.
            yield False
            return
        os.close(descriptor)
        try:
            yield True
        finally:
            path.unlink(missing_ok=True)

    def vector(self, kind, canonical):
        identity = entity_identity(kind, canonical)
        if not canonical.semantic_text.strip():
            return "unavailable", None
        try:
            record = self.read("vectors", digest(identity))
            if record is None:
                return "pending", None
            if not isinstance(record, dict) or "identity" not in record:
                return "error", None
            if record.get("identity") != identity:
                return "pending", None
            if record.get("status") == "error":
                return "error", None
            if record.get("status") != "ranked":
                return "error", None
            vector = record["vector"]
            if record.get("dimensions") != len(vector) or len(vector) != 1024:
                return "error", None
            cosine_similarity(vector, vector)
            return "ranked", vector
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, OverflowError):
            return "error", None

    async def precompute(self, kind, canonical, provider=None, verify_model=None):
        identity = entity_identity(kind, canonical)
        key = digest(identity)
        if self.vector(kind, canonical)[0] == "ranked":
            return
        if not canonical.semantic_text.strip():
            return
        with self.lease(key) as acquired:
            if not acquired or self.vector(kind, canonical)[0] == "ranked":
                return
            try:
                if find_matching_text_privacy_issues(canonical.semantic_text):
                    raise ValueError("Unsupported contact in canonical input")
                if verify_model is None:
                    await verify_current_model()
                else:
                    await verify_model()
                result = await (provider or get_embedding_provider()).embed_many([canonical.semantic_text])
                # Reject a model replacement during generation as well.
                if verify_model is None:
                    await verify_current_model()
                if (len(result.vectors) != 1 or result.dimensions != 1024
                    or result.provider != settings.embedding_provider or result.model != settings.embedding_model):
                    raise ValueError("Incompatible embedding response")
                vector = result.vectors[0]
                if len(vector) != result.dimensions:
                    raise ValueError("Invalid dimensions")
                cosine_similarity(vector, vector)
                self.write("vectors", key, {"identity": identity, "status": "ranked",
                    "dimensions": result.dimensions, "vector": vector, "computed_at": time.time()})
            except Exception:
                # Safe persisted status; no provider message, prompt or PII.
                self.write("vectors", key, {"identity": identity, "status": "error", "computed_at": time.time()})

    def save_snapshot(self, binding, rows):
        token = uuid.uuid4().hex
        self.write("snapshots", token, {"binding": binding, "rows": rows, "expires": time.time() + 600})
        return token

    def load_snapshot(self, token, binding):
        try:
            record = self.read("snapshots", token)
            if record is not None and record["expires"] < time.time():
                self._path("snapshots", token).unlink(missing_ok=True)
                return None
            if record is None or record["binding"] != binding:
                return None
            return record["rows"]
        except (OSError, ValueError, KeyError, TypeError):
            return None


async def verify_current_model():
    """Precompute-only read, never performed by applicant list.

    Digest is a deployment pin, not a mutable model-name guess. Deployments that
    replace BGE must update the pin/profile deliberately and invalidate caches.
    """
    async with httpx.AsyncClient(timeout=settings.embedding_timeout_seconds) as client:
        response = await client.get(settings.ollama_base_url.rstrip("/") + "/api/tags")
        response.raise_for_status()
        names = {settings.embedding_model, settings.embedding_model + ":latest"}
        models = [m for m in response.json()["models"] if m.get("name") in names]
        if len(models) != 1 or models[0].get("digest") != settings.ranking_model_digest:
            raise ValueError("Embedding model identity mismatch")
        if (settings.embedding_provider != "ollama" or settings.embedding_model != "bge-m3"
            or settings.embedding_num_ctx != 8192 or settings.embedding_num_batch != 4096):
            raise ValueError("Ranking requires the frozen production profile")
