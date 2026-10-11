"""Exact, version-bound local Ollama chat accounting. No character heuristics.

Ollama 0.34.2 renders the actual chat request without inference; its own verified
llama-server tokenizer counts that rendered prompt. Unknown deployments fail closed.
No prompt, native token IDs, model paths or provider error bodies are logged/stored.
"""
import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.ai.exceptions import AITokenAccountingUnavailableError

EXTRACTION_BUDGET_PROFILE_VERSION = "cv-extraction-budget-v3-context10240"
SUPPORTED_OLLAMA_VERSION = "0.34.2"


@dataclass(frozen=True)
class PromptAccounting:
    prompt_tokens: int
    special_tokens: int
    effective_num_ctx: int


class OllamaRuntimeTokenCounter:
    def __init__(self, base_url, timeout_seconds):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = min(timeout_seconds, 45)
        self.runtime_verified = False

    async def verify_safe_runtime(self):
        """Fallback requires a runtime known to enforce shift=false/truncate=false."""
        if self.runtime_verified:
            return
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                response = await client.get(self.base_url + "/api/version")
                response.raise_for_status()
                if response.json().get("version") != SUPPORTED_OLLAMA_VERSION:
                    raise AITokenAccountingUnavailableError("Extraction runtime safety is not verified.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise AITokenAccountingUnavailableError("Extraction runtime safety verification is unavailable.") from exc
        self.runtime_verified = True

    async def count(self, payload):
        self.runtime_verified = False
        try:
            if urlparse(self.base_url).hostname not in ("localhost", "127.0.0.1", "::1"):
                raise ValueError("Native accounting requires the local runtime")
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                version = await client.get(self.base_url + "/api/version")
                version.raise_for_status()
                if version.json().get("version") != SUPPORTED_OLLAMA_VERSION:
                    raise ValueError("Unverified render-only API version")
                self.runtime_verified = True
                show = await client.post(self.base_url + "/api/show", json={"model": payload["model"]})
                show.raise_for_status()
                info = show.json()
                model_path = re.search(r"^FROM (.+)$", info["modelfile"], re.M).group(1).strip().strip('"')
                architecture = info["model_info"]["general.architecture"]
                trained_ctx = info["model_info"][architecture + ".context_length"]
                # Same messages/schema/options as generation; public runtime renders
                # its own template. Never emulate Qwen's Go/Jinja template locally.
                rendered = await client.post(self.base_url + "/api/chat", json={**payload, "_debug_render_only": True})
                rendered.raise_for_status()
                envelope = rendered.json()
                if envelope.get("message", {}).get("content") or envelope.get("eval_count", 0):
                    raise ValueError("Render-only runtime generated content")
                prompt = envelope["_debug_info"]["rendered_template"]
                if not isinstance(prompt, str) or not prompt:
                    raise ValueError("Missing rendered prompt")
                for command in await self._runner_commands():
                    port = re.search(r"--port[ =]+(\d+)", command)
                    ctx = re.search(r"(?:--ctx-size|-c)[ =]+(\d+)", command)
                    if not port or not ctx or not 1 <= int(port[1]) <= 65535:
                        continue
                    native = "http://127.0.0.1:" + port[1]
                    props = await client.get(native + "/props")
                    props.raise_for_status()
                    data = props.json()
                    if Path(data.get("model_path", "")).resolve() != Path(model_path).resolve():
                        continue
                    # Do not guess per-sequence capacity on an unverified parallel runner.
                    parallel = re.search(r"(?:--parallel|-np)[ =]+(\d+)", command)
                    if parallel and int(parallel[1]) != 1:
                        raise ValueError("Unverified parallel token capacity")
                    async def tokens(special):
                        response = await client.post(native + "/tokenize", json={"content": prompt, "add_special": special})
                        response.raise_for_status()
                        values = response.json()["tokens"]
                        if not isinstance(values, list) or any(isinstance(v, bool) or not isinstance(v, int) for v in values):
                            raise ValueError("Invalid token accounting")
                        return len(values)
                    plain = await tokens(False)
                    full = await tokens(True)
                    if full < plain:
                        raise ValueError("Invalid special token accounting")
                    return PromptAccounting(plain, full - plain, min(int(ctx[1]), trained_ctx, payload["options"]["num_ctx"]))
                raise ValueError("No verified same-model tokenizer")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise AITokenAccountingUnavailableError("Authoritative extraction token accounting is unavailable.") from exc

    @staticmethod
    async def _runner_commands():
        if os.name != "nt":
            raise ValueError("Native discovery is not verified on this platform")
        command = "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'llama-server.exe' } | Select-Object CommandLine | ConvertTo-Json -Compress"
        process = await asyncio.create_subprocess_exec("powershell", "-NoProfile", "-Command", command,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode != 0:
            raise ValueError("Runtime discovery failed")
        items = json.loads(stdout.decode("utf-8-sig"))
        if isinstance(items, dict):
            items = [items]
        return [item["CommandLine"] for item in (items or []) if isinstance(item.get("CommandLine"), str)]
