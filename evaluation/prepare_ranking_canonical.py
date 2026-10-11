"""Offline production extraction/mapping. Never embeds, scores, or connects to DB."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError

from app.ai.factory import create_ai_provider
from app.core.config import settings
from app.models.job import JobStatus
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.partial_date import DATE_CONTRACT_VERSION
from app.services.cv_date_evidence import EVIDENCE_CONTRACT_VERSION
from app.services.cv_source_consistency import validate_source_grounded,validated_instance_context
from app.schemas.source_date_consistency import CONSISTENCY_VERSION
from app.schemas.matching import CanonicalCVMatchingInput, CanonicalJobMatchingInput
from app.services import matching_input_mapper as mapper
from app.services.matching_fingerprint import fingerprint_cv, fingerprint_job
from app.services.matching_text_privacy import (
    MATCHING_CANONICAL_VERSION, find_matching_text_privacy_issues, find_cv_identity_overlaps,
    identity_fields_influence_matching,
)
from app.services.cv_structured_extraction_service import (
    CVAIContextLimitError, CVAIProviderRequestError, CVAIProviderUnavailableError,
    CVExtractionValidationError, CVStructuredExtractionError, CVStructuredExtractionService,
)
from evaluation.common import EvaluationDataError, iter_csv
from evaluation.labeling_store import atomic_csv, locate_source
from evaluation.ranking_dataset import sources, validate

TASK = '14C.1.5'
GROUND_SHA = 'a7225aeb073f343c55e283b99b6dd5a38cca426e3ab44a86945d0c5e2cd0e36d'
MANIFEST_FIELDS = ['ranking_case_id', 'pair_id', 'cv_id', 'job_id',
                   'canonical_cv_ref', 'canonical_jd_ref', 'ready_for_scoring']
IDENTITY_FIELDS = MANIFEST_FIELDS[:4]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entity_uuid(kind, source_id):
    # External identities remain in the envelope. Mapper requires UUIDs.
    return uuid.uuid5(uuid.NAMESPACE_URL, f'gjob:ranking-canonical:{kind}:{source_id}')


def atomic_json(path, value, *, lines=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.canonical-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            if lines:
                for item in value:
                    handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n')
            else:
                json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def resolve(source_id, ref, entities):
    item = entities.get(source_id)
    if not item or item['ref'] != ref or not item.get('text', '').strip():
        raise EvaluationDataError('SOURCE_NOT_FOUND_OR_REFERENCE_MISMATCH')
    return item


def canonical_cv(cv_id, structured, *, validation_context=None):
    structured = StructuredCVExtractionResult.model_validate(structured,context=validation_context)
    validation_context=validation_context or validated_instance_context(structured)
    full = mapper.build_cv_matching_input(SimpleNamespace(id=entity_uuid('cv', cv_id)), structured)
    # Personal info/address is not an embedding feature. Minimize persisted metadata,
    # but assert EXACT semantic equivalence rather than sanitizing ranking features.
    private = structured.model_dump(mode='json')
    private['personal_info'] = {}
    minimized = StructuredCVExtractionResult.model_validate(private,context=validation_context)
    result = mapper.build_cv_matching_input(SimpleNamespace(id=entity_uuid('cv', cv_id)), minimized)
    if identity_fields_influence_matching(full.semantic_text, result.semantic_text):
        raise EvaluationDataError('PRIVACY_PROJECTION_CHANGED_SEMANTIC_TEXT')
    # Structural identity independence was asserted above. Substring overlap is
    # diagnostic only: an occupation can legitimately occur in professional fields.
    assert_professional_text(result.semantic_text)
    if not result.semantic_text.strip():
        raise EvaluationDataError('EMPTY_CANONICAL_SEMANTIC_TEXT')
    return result, minimized


def assert_professional_text(text):
    # Shared audit only. All text transformations happen in the production mapper.
    if find_matching_text_privacy_issues(text):
        raise EvaluationDataError('SENSITIVE_VALUE_IN_SEMANTIC_TEXT')


def canonical_jd(job_id, raw):
    if not raw.get('title', '').strip() or not raw.get('description', '').strip():
        raise EvaluationDataError('SOURCE_NOT_FOUND_OR_EMPTY_JD')
    # There is no corpus-to-production skill/level taxonomy. Never guess one.
    # All selected skills_desc are absent. Future nonempty prose requires a decision,
    # not treating an arbitrary paragraph as one skill or splitting it heuristically.
    if raw.get('skills_desc', '').strip():
        raise EvaluationDataError('JD_SKILL_MAPPING_NOT_DEFINED')
    job = SimpleNamespace(
        id=entity_uuid('job', job_id), title=raw['title'], description=raw['description'],
        requirements=None, skills=[], location=None, industry=None, employment_type=None,
        experience_level=None, level=None, experience_requirement=None, work_mode=None,
        status=JobStatus.APPROVED, salary_type=None, salary_min=None, salary_max=None,
        salary_fixed=None, salary_currency=raw.get('currency') or 'USD', vacancies=1,
    )
    result = mapper.build_job_matching_input(job)
    assert_professional_text(result.semantic_text)
    return result


def profile():
    root = Path(__file__).resolve().parents[1]
    files = ['app/services/matching_input_mapper.py', 'app/schemas/matching.py',
             'app/services/matching_text_privacy.py',
             'app/services/matching_fingerprint.py',
             'app/schemas/cv.py', 'app/schemas/cv_extraction.py',
             'app/schemas/partial_date.py',
             'app/services/cv_date_evidence.py',
             'app/services/cv_experience_alignment.py',
             'app/services/cv_source_consistency.py','app/schemas/source_date_consistency.py',
             'app/ai/cv_extraction_prompt.py', 'app/ai/ollama_provider.py',
             'app/services/cv_structured_extraction_service.py',
             'evaluation/prepare_ranking_canonical.py']
    return {'task': TASK, 'provider': 'ollama', 'model': settings.ollama_llm_model,
            'extraction_date_contract': DATE_CONTRACT_VERSION,
            'date_evidence_contract': EVIDENCE_CONTRACT_VERSION,
            'source_consistency_contract':CONSISTENCY_VERSION,
            'canonical_version': MATCHING_CANONICAL_VERSION,
            'num_ctx': settings.ollama_llm_num_ctx, 'timeout': settings.ollama_llm_timeout_seconds,
            'think': False, 'temperature': 0, 'source_code': {p: file_sha(root/p) for p in files},
            'identity': 'uuid5-gjob-ranking-canonical-v1',
            'jd_projection': 'title-description-only-absent-taxonomy-v1',
            'privacy': 'personal-info-omitted-semantic-equivalence-asserted-v1'}


def envelope(kind, source_id, source, source_hashes, run_profile):
    return {f'{kind}_id': source_id, 'task': TASK, 'source_ref': source['ref'],
            'source_type': 'Resume.csv:Resume_str' if kind == 'cv' else 'job_postings.csv',
            'source_sha256': digest(source), 'source_file_sha256': source_hashes,
            'canonical_version': run_profile.get('canonical_version', MATCHING_CANONICAL_VERSION),
            **({'provider': run_profile.get('provider'), 'model': run_profile.get('model')} if kind == 'cv' else {}),
            'profile_sha256': digest(run_profile), 'generated_at': datetime.now(timezone.utc).isoformat()}


def read_records(path, expected, kind, *, invalidate_incompatible=False, reuse_verified_v3=False,source_texts=None):
    if not path.exists():
        return {}
    records = {}
    seen = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        key = record[f'{kind}_id']
        if key in seen or key not in expected:
            raise EvaluationDataError('DUPLICATE_OR_UNRELATED_CANONICAL_RECORD')
        seen.add(key)
        identity = expected[key]
        for field in ('source_ref', 'source_sha256', 'source_file_sha256'):
            if record[field] != identity[field]:
                raise EvaluationDataError('CANONICAL_RESUME_IDENTITY_MISMATCH')
        migrating = record['profile_sha256'] != identity['profile_sha256']
        if migrating and not reuse_verified_v3:
            if not invalidate_incompatible:
                raise EvaluationDataError('CANONICAL_RESUME_IDENTITY_MISMATCH')
            # Explicit upgrade: old result is not accepted under new extraction
            # contract merely because its JSON schema/text happens to validate.
            continue
        if record['status'] == 'SUCCEEDED':
            cls = CanonicalCVMatchingInput if kind == 'cv' else CanonicalJobMatchingInput
            canonical = cls.model_validate(record['canonical_input'])
            if record.get('canonical_version') != identity['canonical_version']:
                raise EvaluationDataError('CANONICAL_VERSION_MISMATCH')
            fingerprint = fingerprint_cv(canonical) if kind == 'cv' else fingerprint_job(canonical)
            if record.get('canonical_fingerprint') != fingerprint:
                raise EvaluationDataError('CANONICAL_FINGERPRINT_MISMATCH')
            actual_id = canonical.cv_id if kind == 'cv' else canonical.job_id
            if actual_id != entity_uuid(kind, key):
                raise EvaluationDataError('CANONICAL_ENTITY_ID_MISMATCH')
            if canonical.model_dump(mode='json') != record['canonical_input']:
                raise EvaluationDataError('CANONICAL_RECORD_NOT_NORMALIZED')
            if digest(record['canonical_input']) != record['canonical_sha256']:
                raise EvaluationDataError('CANONICAL_RECORD_HASH_MISMATCH')
            if kind == 'cv':
                stored=record['structured_result']
                if any(item.get('date_consistency') for item in stored.get('experiences',[])):
                    if source_texts is None or key not in source_texts:
                        raise EvaluationDataError('SOURCE_CONFLICT_REPLAY_REQUIRES_SOURCE')
                    source=source_texts[key]
                    if digest({'ref':identity['source_ref'],'text':source})!=identity['source_sha256']:
                        raise EvaluationDataError('SOURCE_CONFLICT_REPLAY_SOURCE_MISMATCH')
                    validated,_,_,context=validate_source_grounded(source,stored)
                    if validated.model_dump(mode='json')!=stored:
                        raise EvaluationDataError('SOURCE_CONFLICT_REPLAY_DATA_MISMATCH')
                    rebuilt,_=canonical_cv(key,validated,validation_context=context)
                else:
                    rebuilt, _ = canonical_cv(key, stored)
                if rebuilt != canonical:
                    raise EvaluationDataError('CANONICAL_RECORD_MAPPER_MISMATCH')
            if not canonical.semantic_text.strip():
                raise EvaluationDataError('EMPTY_CANONICAL_RECORD')
            assert_professional_text(canonical.semantic_text)
        if migrating and reuse_verified_v3:
            if record.get('canonical_version') != MATCHING_CANONICAL_VERSION:
                raise EvaluationDataError('CANNOT_REUSE_PRE_V3')
            record['origin_profile_sha256'] = record['profile_sha256']
            record['profile_sha256'] = identity['profile_sha256']
            record['verified_profile_migration'] = True
        records[key] = record
    return records


def backup_checkpoint(path):
    """Preserve byte-identical private checkpoint before an explicit upgrade."""
    if not path.exists():
        return
    root = Path(__file__).resolve().parents[1]
    directory = root/'evaluation/cache/ranking-canonical-history'
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory/(path.stem + '-' + file_sha(path) + path.suffix)
    if destination.exists():
        if file_sha(destination) != file_sha(path):
            raise EvaluationDataError('CHECKPOINT_BACKUP_HASH_MISMATCH')
    else:
        shutil.copyfile(path, destination)


def failure_code(error):
    if isinstance(error, EvaluationDataError) and str(error) == 'AMBIGUOUS_IDENTITY_OVERLAP':
        return 'AMBIGUOUS_IDENTITY_OVERLAP'
    if isinstance(error, CVAIContextLimitError):
        return 'CONTEXT_LIMIT_EXCEEDED'
    if isinstance(error, (CVExtractionValidationError, ValidationError)):
        return 'SCHEMA_VALIDATION_FAILED'
    if isinstance(error, CVAIProviderUnavailableError):
        return 'PROVIDER_UNAVAILABLE'
    if isinstance(error, CVAIProviderRequestError):
        return 'PROVIDER_REQUEST_INVALID'
    if isinstance(error, CVStructuredExtractionError):
        return 'EXTRACTION_FAILED'
    return 'CANONICAL_MAPPING_FAILED'


async def prepare_cvs(expected, sources_by_id, existing, service, path, *, retry_failed=False):
    records = dict(existing)
    for cv_id in sorted(expected):
        if cv_id in records and (records[cv_id]['status'] == 'SUCCEEDED' or not retry_failed):
            continue
        record = dict(expected[cv_id])
        if hasattr(service.provider, 'last_metrics'):
            service.provider.last_metrics = None
        try:
            structured = await service.extract_from_text(sources_by_id[cv_id]['text'])
            canonical, minimized = canonical_cv(cv_id, structured)
            record.update(status='SUCCEEDED', canonical_input=canonical.model_dump(mode='json'),
                          structured_result=minimized.model_dump(mode='json'))
            record['canonical_sha256'] = digest(record['canonical_input'])
            record['canonical_fingerprint'] = fingerprint_cv(canonical)
            record['identity_privacy_audit_passed'] = True
        except (CVStructuredExtractionError, ValidationError, EvaluationDataError) as error:
            record.update(status='FAILED', error_code=failure_code(error))
        metrics = getattr(service.provider, 'last_metrics', None)
        record['generation_metrics'] = asdict(metrics) if metrics else None
        records[cv_id] = record
        atomic_json(path, [records[key] for key in sorted(records)], lines=True)
        print(f'CV progress {len(records)}/{len(expected)} status={record["status"]}', flush=True)
    return records


def pair_manifest(identities, cvs, jds, cv_path, jd_path):
    seen = set()
    result = []
    for row in identities:
        if row['pair_id'] in seen:
            raise EvaluationDataError('DUPLICATE_PAIR')
        seen.add(row['pair_id'])
        cv_ready = cvs.get(row['cv_id'], {}).get('status') == 'SUCCEEDED'
        jd_ready = jds.get(row['job_id'], {}).get('status') == 'SUCCEEDED'
        result.append({**{key: row[key] for key in IDENTITY_FIELDS},
                       'canonical_cv_ref': f'{cv_path.name}#cv_id={row["cv_id"]}',
                       'canonical_jd_ref': f'{jd_path.name}#job_id={row["job_id"]}',
                       'ready_for_scoring': str(cv_ready and jd_ready).lower()})
    return result


async def run(args):
    started = time.perf_counter()
    if file_sha(args.input) != GROUND_SHA:
        raise EvaluationDataError('FROZEN_GROUND_TRUTH_HASH_MISMATCH')
    rows = [row for _, row in iter_csv(args.input)]
    cvs, jds, source_hashes = sources(args.data_dir)
    validate(rows, cvs, jds, labeled=True)
    if len(rows) != 100 or len({r['cv_id'] for r in rows}) != 95 or len({r['job_id'] for r in rows}) != 10:
        raise EvaluationDataError('RANKING_INVENTORY_MISMATCH')
    if settings.ai_provider != 'ollama' or settings.ollama_llm_model != 'qwen3:8b':
        raise EvaluationDataError('CONFIGURE_EXISTING_OLLAMA_QWEN_PROVIDER')
    run_profile = profile()
    # Read source metadata only, never pass label/reason/job into CV extraction.
    identities = [{key: r[key] for key in IDENTITY_FIELDS} for r in rows]
    cv_sources, jd_sources = {}, {}
    for row in rows:
        cv_sources[row['cv_id']] = resolve(row['cv_id'], row['candidate_source_ref'], cvs)
        jd_sources[row['job_id']] = resolve(row['job_id'], row['job_source_ref'], jds)
    selected_jobs = set(jd_sources)
    raw_jobs = {raw['job_id']: raw for _, raw in iter_csv(locate_source(args.data_dir, 'job_postings.csv'))
                if raw['job_id'] in selected_jobs}
    cv_expected = {cid: envelope('cv', cid, src, source_hashes, run_profile) for cid, src in cv_sources.items()}
    jd_expected = {jid: envelope('job', jid, {**src, 'raw': raw_jobs[jid]}, source_hashes, run_profile)
                   for jid, src in jd_sources.items()}
    cv_path = args.input.parent/'ranking_canonical_cvs.jsonl'
    jd_path = args.input.parent/'ranking_canonical_jds.jsonl'
    manifest_path = args.input.parent/'ranking_canonical_pair_manifest.csv'
    summary_path = args.output/'summary.json'
    if summary_path.exists():
        old = json.loads(summary_path.read_text(encoding='utf-8'))
        if old.get('frozen'):
            if args.refresh_jd_drafts or args.invalidate_incompatible_checkpoints:
                raise EvaluationDataError('CANNOT_REFRESH_FROZEN_CANONICAL_INPUTS')
            for p, key in ((cv_path, 'canonical_cv_sha256'), (jd_path, 'canonical_jd_sha256'),
                           (manifest_path, 'manifest_sha256'), (args.input, 'ground_truth_sha256')):
                if file_sha(p) != old[key]:
                    raise EvaluationDataError('FROZEN_ARTIFACT_HASH_MISMATCH')
            if old['profile'] != run_profile:
                raise EvaluationDataError('FROZEN_PROFILE_MISMATCH')
            read_records(cv_path, cv_expected, 'cv',source_texts={k:v['text'] for k,v in cv_sources.items()})
            read_records(jd_path, jd_expected, 'job')
            print('Already frozen; no provider calls.', flush=True)
            return
    # One process owns checkpoints. Stale lock is never removed automatically.
    args.output.mkdir(parents=True, exist_ok=True)
    lock = args.output/'preparation.lock'
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(str(os.getpid()))
    try:
        cv_records = read_records(cv_path, cv_expected, 'cv',
                                  invalidate_incompatible=args.invalidate_incompatible_checkpoints,
                                  reuse_verified_v3=args.reuse_verified_v3,
                                  source_texts={k:v['text'] for k,v in cv_sources.items()})
        if args.refresh_jd_drafts:
            if cv_path.exists():
                raise EvaluationDataError('JD_DRAFT_REFRESH_REQUIRES_NO_CV_CHECKPOINT')
            # Explicit representation upgrade, never automatic on startup. Verify
            # old draft provenance before rebuilding all JDs through the new mapper.
            if jd_path.exists():
                for line in jd_path.read_text(encoding='utf-8').splitlines():
                    old_record = json.loads(line)
                    expected = jd_expected.get(old_record['job_id'])
                    if expected is None or any(old_record[key] != expected[key] for key in
                            ('source_ref', 'source_sha256', 'source_file_sha256')):
                        raise EvaluationDataError('JD_DRAFT_SOURCE_IDENTITY_MISMATCH')
            jd_records = {}
        else:
            jd_records = read_records(jd_path, jd_expected, 'job',
                                      invalidate_incompatible=args.invalidate_incompatible_checkpoints,
                                      reuse_verified_v3=args.reuse_verified_v3)
        if args.invalidate_incompatible_checkpoints or args.reuse_verified_v3:
            # Both source checks above must pass before writing any backup/output.
            backup_checkpoint(cv_path)
            backup_checkpoint(jd_path)
        for jid in sorted(jd_expected):
            if jid in jd_records and jd_records[jid]['status'] == 'SUCCEEDED':
                if canonical_jd(jid, raw_jobs[jid]).model_dump(mode='json') != jd_records[jid]['canonical_input']:
                    raise EvaluationDataError('JD_RESUME_MAPPER_MISMATCH')
                continue
            record = dict(jd_expected[jid])
            try:
                canonical = canonical_jd(jid, raw_jobs[jid])
                record.update(status='SUCCEEDED', canonical_input=canonical.model_dump(mode='json'))
                record['canonical_sha256'] = digest(record['canonical_input'])
                record['canonical_fingerprint'] = fingerprint_job(canonical)
            except EvaluationDataError as error:
                record.update(status='FAILED', error_code=str(error))
            except ValidationError:
                record.update(status='FAILED', error_code='SCHEMA_VALIDATION_FAILED')
            jd_records[jid] = record
        atomic_json(jd_path, [jd_records[key] for key in sorted(jd_records)], lines=True)
        if any(record['status'] != 'SUCCEEDED' for record in jd_records.values()):
            # Resolve representation/privacy blockers BEFORE spending CV inference.
            manifest = pair_manifest(identities, cv_records, jd_records, cv_path, jd_path)
            atomic_csv(manifest_path, manifest, MANIFEST_FIELDS)
            atomic_json(summary_path, {
                'task': TASK, 'status': 'BLOCKED', 'frozen': False,
                'ready_for_task_14c2': False, 'ground_truth_sha256': GROUND_SHA,
                'pairs': 100, 'unique_cvs': 95, 'unique_jds': 10,
                'canonical_cv_success': sum(r['status'] == 'SUCCEEDED' for r in cv_records.values()),
                'canonical_jd_success': sum(r['status'] == 'SUCCEEDED' for r in jd_records.values()),
                'ready_pairs': sum(r['ready_for_scoring'] == 'true' for r in manifest),
                'failures': {k: r['error_code'] for k, r in jd_records.items() if r['status'] != 'SUCCEEDED'},
                'profile': run_profile, 'runtime_seconds': time.perf_counter()-started,
                'canonical_cv_sha256': file_sha(cv_path) if cv_path.exists() else None,
                'canonical_jd_sha256': file_sha(jd_path), 'manifest_sha256': file_sha(manifest_path),
                'semantic_scores_created': False, 'ranking_metrics_computed': False,
            })
            print('BLOCKED: JD preparation failed; no CV generation started.', flush=True)
            return
        # Provider construction is not a request. No cloud fallback is possible.
        provider = create_ai_provider()
        service = CVStructuredExtractionService(provider=provider,
                                               correction_only=args.final_schema_correction)
        cv_records = await prepare_cvs(cv_expected, cv_sources, cv_records, service, cv_path,
                                       retry_failed=args.retry_failed)
        atomic_json(cv_path, [cv_records[key] for key in sorted(cv_records)], lines=True)
        manifest = pair_manifest(identities, cv_records, jd_records, cv_path, jd_path)
        atomic_csv(manifest_path, manifest, MANIFEST_FIELDS)
        ready = sum(r['ready_for_scoring'] == 'true' for r in manifest)
        if file_sha(args.input) != GROUND_SHA:
            raise EvaluationDataError('GROUND_TRUTH_CHANGED_DURING_PREPARATION')
        summary = {'task': TASK, 'status': 'PASS' if ready == 100 else 'BLOCKED',
                   'frozen': ready == 100, 'ready_for_task_14c2': ready == 100,
                   'pairs': 100, 'unique_cvs': 95, 'unique_jds': 10, 'ready_pairs': ready,
                   'canonical_cv_success': sum(r['status'] == 'SUCCEEDED' for r in cv_records.values()),
                   'canonical_jd_success': sum(r['status'] == 'SUCCEEDED' for r in jd_records.values()),
                   'ground_truth_sha256': GROUND_SHA, 'profile': run_profile,
                   'canonical_cv_sha256': file_sha(cv_path), 'canonical_jd_sha256': file_sha(jd_path),
                   'manifest_sha256': file_sha(manifest_path), 'runtime_seconds': time.perf_counter()-started,
                   'failures': {k: r['error_code'] for k, r in cv_records.items() if r['status'] != 'SUCCEEDED'},
                   'semantic_scores_created': False, 'ranking_metrics_computed': False}
        atomic_json(summary_path, summary)
        print(json.dumps({k: summary[k] for k in ('status', 'canonical_cv_success', 'canonical_jd_success', 'ready_pairs')}, sort_keys=True))
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('evaluation/data/derived/ranking_pairs_labeled.csv'))
    parser.add_argument('--data-dir', type=Path, default=Path('C:/DATN/Datasets'))
    parser.add_argument('--output', type=Path, default=Path('evaluation/results/ranking-canonical-inputs'))
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--refresh-jd-drafts', action='store_true',
                        help='Explicitly rebuild unfrozen JD drafts after a representation upgrade; requires no CV checkpoint.')
    parser.add_argument('--invalidate-incompatible-checkpoints', action='store_true',
                        help='Explicit contract upgrade: back up old source-verified checkpoints and recompute incompatible items.')
    parser.add_argument('--reuse-verified-v3', action='store_true',
                        help='Revalidate same-v3 source/fingerprint/schema/mapper and preserve extraction provenance across runtime recovery.')
    parser.add_argument('--final-schema-correction', action='store_true',
                        help='One final generation with the shared production correction policy; no nested schema retry.')
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
