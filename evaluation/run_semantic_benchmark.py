"""Offline measurement of existing semantic-v1; no DB, extraction or production APIs."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import math
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from evaluation.benchmark_metrics import analyze, classification, errors
from evaluation.common import EvaluationDataError, PAIR_TYPES, iter_csv, resolve_dataset_files
from evaluation.labeling_store import atomic_csv
from evaluation.validate_labels import validate_labeled_file

ADAPTER_VERSION = 'raw-source-normalized-v1'
PREDICTION_FIELDS = ['pair_id', 'cv_id', 'job_id', 'human_label', 'semantic_score',
                     'predicted_label', 'candidate_type', 'label_reason']


def context_provider(base_url, model, timeout, num_ctx, num_batch=8192):
    """Offline-only request configuration; reuse production response/error validation."""
    from app.embeddings.ollama_provider import OllamaEmbeddingProvider
    from app.embeddings.exceptions import EmbeddingProviderResponseError, EmbeddingProviderUnavailableError

    class OfflineContextProvider(OllamaEmbeddingProvider):
        async def embed_many(self, texts):
            if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
                raise EvaluationDataError('Embedding inputs must be non-empty text.')
            try:
                async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
                    response = await client.post('/api/embed', json={
                        'model': model, 'input': list(texts), 'truncate': False,
                        'options': {'num_ctx': num_ctx, 'num_batch': num_batch}})
            except httpx.RequestError as exc:
                raise EmbeddingProviderUnavailableError('Embedding provider unavailable.') from exc
            if not response.is_success:
                self._raise_http_error(response)
            try:
                payload = response.json()
            except ValueError as exc:
                raise EmbeddingProviderResponseError('Unreadable embedding JSON.') from exc
            return self._validate_response(payload, expected_count=len(texts))

    return OfflineContextProvider(base_url=base_url, model=model, timeout_seconds=timeout)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_benchmark(input_path, data_dir, expected_count=220):
    # Validator writes only to disposable staging; never normalize/overwrite human input.
    with tempfile.TemporaryDirectory(prefix='gjob-benchmark-validation-') as tmp:
        validated = validate_labeled_file(input_path, Path(tmp) / 'validated.csv', data_dir=data_dir)
    if validated['rows'] != expected_count:
        raise EvaluationDataError(f'Expected {expected_count} labeled pairs; got {validated["rows"]}.')
    return sorted((r for _, r in iter_csv(Path(input_path))), key=lambda r: r['pair_id']), validated


def prepare_sources(rows, data_dir):
    # Exact existing whitespace/section helpers, but no fabricated structured CV fields.
    from app.services.matching_input_mapper import normalize_multiline_text, _section, _semantic_text
    files = resolve_dataset_files(data_dir)
    cvs, jobs = {}, {}
    wanted_cv, wanted_jd = {r['cv_id'] for r in rows}, {r['job_id'] for r in rows}
    for _, raw in iter_csv(files['Resume.csv']):
        cid = raw['ID'].strip()
        if cid in wanted_cv:
            if cid in cvs:
                raise EvaluationDataError('Ambiguous CV source ID.')
            cvs[cid] = normalize_multiline_text(raw['Resume_str'])
    for _, raw in iter_csv(files['job_postings.csv']):
        jid = raw['job_id'].strip()
        if jid in wanted_jd:
            if jid in jobs:
                raise EvaluationDataError('Ambiguous JD source ID.')
            jobs[jid] = _semantic_text((_section('TITLE', [raw['title']]),
                _section('DESCRIPTION', [raw['description']]), _section('SKILLS', [raw.get('skills_desc')])))
    if set(cvs) != wanted_cv or set(jobs) != wanted_jd or any(not t for t in [*cvs.values(), *jobs.values()]):
        raise EvaluationDataError('Missing or empty referenced source text.')
    return cvs, jobs, files


class CachedVectors:
    def __init__(self, provider, directory, identity, force=False):
        self.provider, self.directory, self.identity, self.force = provider, Path(directory), identity, force
        self.by_text = {}; self.hits = self.misses = 0
        self.metadata = None

    def key(self, kind, entity_id, text):
        raw = json.dumps([self.identity, kind, entity_id, hashlib.sha256(text.encode()).hexdigest()], sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def accept(self, payload, text):
        from app.services.semantic_matching_service import cosine_similarity
        expected_model = self.identity.get('model')
        if expected_model and payload['model'].removesuffix(':latest') != expected_model.removesuffix(':latest'):
            raise EvaluationDataError('Embedding model does not match the benchmark identity.')
        if self.identity.get('provider') and payload['provider'] != self.identity['provider']:
            raise EvaluationDataError('Embedding provider does not match the benchmark identity.')
        vector = tuple(payload['vector'])
        cosine_similarity(vector, vector)  # finite, nonzero, strict numeric validation
        metadata = (payload['provider'], payload['model'], payload['dimensions'])
        if len(vector) != metadata[2] or (self.metadata and metadata != self.metadata):
            raise EvaluationDataError('Embedding cache/provider metadata mismatch.')
        self.metadata = metadata
        self.by_text[text] = vector

    async def preload(self, cvs, jobs, batch_size):
        pending = []
        for kind, texts in [('cv', cvs), ('job', jobs)]:
            for entity_id, text in sorted(texts.items()):
                key = self.key(kind, entity_id, text); path = self.directory / f'{key}.json'
                if path.exists() and not self.force:
                    payload = json.loads(path.read_text(encoding='utf-8'))
                    if payload.get('key') != key or payload.get('identity') != self.identity:
                        raise EvaluationDataError('Embedding cache identity mismatch.')
                    self.accept(payload, text); self.hits += 1
                else:
                    pending.append((key, path, text)); self.misses += 1
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset:offset + batch_size]
            result = await self.provider.embed_many([item[2] for item in batch])
            if len(result.vectors) != len(batch):
                raise EvaluationDataError('Provider returned incorrect vector count.')
            for (key, path, text), vector in zip(batch, result.vectors, strict=True):
                payload = dict(key=key, identity=self.identity, vector=list(vector),
                               provider=result.provider, model=result.model, dimensions=result.dimensions)
                self.accept(payload, text)
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as staging:
                    json.dump(payload, staging); name = staging.name
                Path(name).replace(path)
            print(f'Embeddings: {min(offset + batch_size, len(pending))}/{len(pending)} misses completed', flush=True)

    async def embed_many(self, texts):
        from app.embeddings.base import EmbeddingBatchResult
        if self.metadata is None:
            raise EvaluationDataError('Embedding cache is not prepared.')
        provider, model, dimensions = self.metadata
        return EmbeddingBatchResult(tuple(self.by_text[t] for t in texts), provider, model, dimensions)


async def score_pairs(rows, cvs, jobs, cache, threshold):
    from app.models.job import JobStatus
    from app.schemas.matching import CanonicalCVMatchingInput, CanonicalJobMatchingInput, CanonicalSalaryMetadata
    from app.services.semantic_matching_service import SemanticMatchingService
    service = SemanticMatchingService(cache)
    predictions = []
    for row in rows:
        cid, jid = row['cv_id'], row['job_id']
        cv = CanonicalCVMatchingInput(cv_id=uuid.uuid5(uuid.NAMESPACE_URL, 'cv:' + cid), skills=[],
            experiences=[], educations=[], projects=[], certificates=[], languages=[], semantic_text=cvs[cid])
        job = CanonicalJobMatchingInput(job_id=uuid.uuid5(uuid.NAMESPACE_URL, 'job:' + jid), title='source job',
            description=jobs[jid], skills=[], status=JobStatus.APPROVED,
            salary=CanonicalSalaryMetadata(currency='VND'), vacancies=1, semantic_text=jobs[jid])
        result = await service.match(cv, job)
        score = result.semantic_similarity
        predictions.append(dict(pair_id=row['pair_id'], cv_id=cid, job_id=jid,
            human_label=row['label'], semantic_score=score, predicted_label=int(score >= threshold),
            candidate_type=row['pair_type'], label_reason=row['label_reason']))
    return predictions


def summarize(predictions, threshold):
    main = analyze(predictions, threshold)
    groups = {kind: analyze([r for r in predictions if r['candidate_type'] == kind], threshold) for kind in PAIR_TYPES}
    labels = [int(r['human_label']) for r in predictions]; scores = [r['semantic_score'] for r in predictions]
    grid = sorted({round(-1 + i * .05, 6) for i in range(41)} | {threshold} | set(scores))
    grid.append(math.nextafter(max(scores), math.inf))  # all-negative boundary
    thresholds = [classification(labels, scores, t) for t in sorted(set(grid))]
    best = max(thresholds, key=lambda r: (r['f1'] if r['f1'] is not None else -1, r['threshold']))
    return dict(overall=main, groups=groups, best_exploratory_f1_threshold=best,
                threshold_warning='This is an in-sample exploratory threshold estimate, not a held-out production calibration.'), thresholds


def write_reports(out, predictions, metrics, thresholds):
    out.mkdir(parents=True, exist_ok=True)
    atomic_csv(out / 'predictions.csv', predictions, PREDICTION_FIELDS)
    atomic_csv(out / 'threshold_analysis.csv', thresholds, list(thresholds[0]))
    for filename, rows in [('false_positives.csv', errors(predictions, 0)), ('false_negatives.csv', errors(predictions, 1)),
            ('hard_negative_errors.csv', sorted((r for r in predictions if r['candidate_type'] == 'HARD_NEGATIVE_CANDIDATE' and r['human_label'] == '0'), key=lambda r: (-r['semantic_score'], r['pair_id'])))]:
        atomic_csv(out / filename, rows, PREDICTION_FIELDS)
    (out / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    overall = metrics['overall']
    lines = ['# Semantic-v1 Benchmark', '', '## 1. Objective', '',
        f'Evaluate existing semantic-v1 against {len(predictions)} human-reviewed pairs, offline.', '',
        '## 2. Ground Truth', '', 'Only label/label_reason are ground truth. AI suggestions assisted the reviewer; sampling groups are not labels.', '',
        '## 3. Dataset', '', f"Human positives: {overall['human_positive']}; negatives: {overall['human_negative']}.", '',
        '## 4. Semantic-v1 Implementation', '',
        'Reuses app.services.semantic_matching_service.SemanticMatchingService.match and cosine_similarity unchanged.',
        'Score = dot(CV, JD) / (norm(CV) * norm(JD)), raw range [-1, 1]. No weighted title/skills rules.',
        f"Embedding model: {metrics['reproducibility']['model']}; adapter: {ADAPTER_VERSION}.",
        'CV uses original Resume_str with existing normalize_multiline_text. JD uses existing TITLE/DESCRIPTION/SKILLS section helpers and skills_desc.',
        'This isolates matching from extraction. It is not an end-to-end evaluation of production structured-CV preprocessing.',
        'No invented skill-code meanings, structured fields, industry/experience enums, or LLM extraction.', '',
        f"Offline embedding options: num_ctx={metrics['reproducibility'].get('identity', {}).get('num_ctx')}, num_batch={metrics['reproducibility'].get('identity', {}).get('num_batch')}, truncate=false.",
        'The unchanged production request failed on full-text inputs. num_ctx alone still failed; explicit encoder num_batch was required by local Ollama.',
        'These are documented offline full-text runtime settings, not a production configuration change.', '',
        '## 5. Default Threshold', '', f'Evaluation threshold: {overall["threshold"]}. No production classification threshold was found; this is an evaluation assumption.', '',
        '## 6. Main Results', '', '| Metric | Result |', '|---|---:|']
    for key in ('precision', 'recall', 'f1', 'accuracy', 'specificity', 'roc_auc', 'average_precision', 'balanced_accuracy', 'mcc'):
        lines.append(f'| {key} | {overall[key]} |')
    lines += ['', 'PR-AUC is reported as non-interpolated Average Precision; undefined metrics are null, not fabricated zeros.', '',
        '## 7. Confusion Matrix', '', f"TP={overall['TP']}, TN={overall['TN']}, FP={overall['FP']}, FN={overall['FN']}", '',
        '## 8. Threshold Analysis', '', metrics['threshold_warning'],
        f"Exploratory best F1: {metrics['best_exploratory_f1_threshold']}", 'Production threshold was not changed.', '',
        '## 9. Candidate Group Analysis', '', '| Group | Count | Human + / - | FP / FN | F1 | Accuracy |', '|---|---:|---|---|---:|---:|']
    for group, result in metrics['groups'].items():
        lines.append(f"| {group} | {result['count']} | {result['human_positive']} / {result['human_negative']} | {result['FP']} / {result['FN']} | {result['f1']} | {result['accuracy']} |")
    lines += ['', '## 10. Hard Negative Analysis', '',
        f"Hard-group FPR among human negatives: {metrics['groups']['HARD_NEGATIVE_CANDIDATE']['false_positive_rate']}.",
        'hard_negative_errors.csv lists all hard-group human negatives, highest score first; predictions identify which are false positives.',
        'Easy-group success must not obscure hard-group errors; sampling groups can contain human positives.', '',
        '## 11. False Positives', '', f"Count: {overall['FP']}. See false_positives.csv, highest score first.", '',
        '## 12. False Negatives', '', f"Count: {overall['FN']}. See false_negatives.csv, lowest score first.", '',
        '## 13. Limitations', '',
        '220-pair, single-human-reviewer, difficulty-focused sample; not representative production prevalence.',
        'In-sample threshold analysis is not held-out calibration. No baseline comparison. Matching, not extraction, is measured.',
        'Raw-source adapter differs from structured production CV representation and may retain incidental source text.',
        'ROC-AUC/AP evaluate pooled pair ranking, not a representative per-job candidate ranking test.', '',
        '## 14. Conclusion', '', 'Results describe measured semantic-v1 behavior only; no superiority over baseline-v1 is claimed.', '',
        '## 15. Next Step', '', 'Run baseline-v1 against the exact same human-labeled pairs, with a documented deterministic adapter.', '',
        '## Reproducibility', '', '```json', json.dumps(metrics['reproducibility'], indent=2), '```']
    lines += ['', '## Highest-scoring false positives / Lowest-scoring false negatives', '',
              '| Error | Pair ID | Score | Sampling group |', '|---|---|---:|---|']
    for kind, label in [('FP', 0), ('FN', 1)]:
        for row in errors(predictions, label)[:5]:
            lines.append(f"| {kind} | {row['pair_id']} | {row['semantic_score']} | {row['candidate_type']} |")
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


async def run(args):
    started = time.perf_counter()
    input_hash = sha(args.input)
    rows, validation = load_benchmark(args.input, args.data_dir)
    if args.limit:
        rows = rows[:args.limit]
    cvs, jobs, files = prepare_sources(rows, args.data_dir)
    source_hashes = {name: sha(files[name]) for name in ('Resume.csv', 'job_postings.csv')}
    from app.core.config import settings
    from app.services import semantic_matching_service
    model = args.model or settings.embedding_model
    base_url = args.base_url or settings.ollama_base_url
    parsed = urlparse(base_url)
    if parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'} or parsed.username or parsed.password:
        raise EvaluationDataError('Offline benchmark requires loopback Ollama URL.')
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(base_url.rstrip('/') + '/api/tags')
        response.raise_for_status()
        matches = [m for m in response.json()['models'] if m['name'] in {model, model + ':latest'}]
        show = await client.post(base_url.rstrip('/') + '/api/show', json={'model': model})
        show.raise_for_status()
        capacities = [value for key, value in show.json().get('model_info', {}).items() if key.endswith('.context_length')]
    if len(matches) != 1 or not matches[0].get('digest'):
        raise EvaluationDataError('Configured embedding model/digest not available.')
    if len(capacities) != 1 or args.num_ctx > capacities[0]:
        raise EvaluationDataError('Offline embedding context exceeds confirmed model capacity.')
    identity = dict(model=matches[0]['name'], digest=matches[0]['digest'], provider='ollama',
                    adapter=ADAPTER_VERSION, core_sha256=sha(semantic_matching_service.__file__), base_url=base_url,
                    num_ctx=args.num_ctx, num_batch=args.num_batch, truncate=False, adapter_sha256=hashlib.sha256(
                        (inspect.getsource(prepare_sources) + inspect.getsource(context_provider)).encode()).hexdigest())
    cache = CachedVectors(context_provider(base_url, model, settings.embedding_timeout_seconds, args.num_ctx, args.num_batch),
        args.cache_dir, identity, args.force_recompute)
    await cache.preload(cvs, jobs, args.batch_size)
    predictions = await score_pairs(rows, cvs, jobs, cache, args.threshold)
    metrics, thresholds = summarize(predictions, args.threshold)
    try:
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    if sha(args.input) != input_hash:
        raise EvaluationDataError('Human input changed during benchmark; refusing publication.')
    if source_hashes != {name: sha(files[name]) for name in source_hashes}:
        raise EvaluationDataError('Source data changed during benchmark; refusing publication.')
    metrics.update(validation=validation, cache_hits=cache.hits, cache_misses=cache.misses,
        unique_cvs=len(cvs), unique_jobs=len(jobs), elapsed_seconds=time.perf_counter() - started,
        reproducibility=dict(input=str(Path(args.input).resolve()), input_sha256=input_hash,
            source_hashes=source_hashes,
            implementation='app.services.semantic_matching_service.SemanticMatchingService.match',
            identity=identity, model=model, score_range=[-1, 1], threshold=args.threshold,
            threshold_grid=[r['threshold'] for r in thresholds], git_commit=commit,
            timestamp=datetime.now(timezone.utc).isoformat(), command=sys.argv, partial=bool(args.limit),
            unique_cvs=len(cvs), unique_jobs=len(jobs)))
    write_reports(Path(args.output_dir), predictions, metrics, thresholds)
    print(json.dumps({k: v for k, v in metrics.items() if k != 'reproducibility'}, indent=2), flush=True)
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True); parser.add_argument('--data-dir', required=True)
    parser.add_argument('--output-dir', default='evaluation/results/semantic-v1')
    parser.add_argument('--cache-dir', default='evaluation/cache/semantic-v1')
    parser.add_argument('--threshold', type=float, default=.5)
    parser.add_argument('--batch-size', type=int, default=4)
    parser.add_argument('--num-ctx', type=int, default=8192, help='Offline embedding context only; bounded by model metadata.')
    parser.add_argument('--num-batch', type=int, default=8192, help='Offline encoder batch capacity, not text batch count.')
    parser.add_argument('--force-recompute', action='store_true')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--model'); parser.add_argument('--base-url')
    args = parser.parse_args(argv)
    if not math.isfinite(args.threshold) or not -1 <= args.threshold <= 1 or args.batch_size < 1 or args.num_ctx < 1 or not 1 <= args.num_batch <= args.num_ctx or (args.limit is not None and args.limit < 1):
        parser.error('Invalid threshold, batch size or limit.')
    if Path(args.output_dir).resolve() == Path(args.cache_dir).resolve():
        parser.error('Output and cache must be separate.')
    if any((Path(args.output_dir) / name).exists() for name in ('predictions.csv', 'metrics.json', 'report.md')):
        parser.error('Results already exist; use a new --output-dir to preserve previous measurements.')
    try:
        asyncio.run(run(args))
    except Exception as exc:
        # Provider responses/input text may appear in exception details; never print them.
        raise SystemExit(f'Benchmark failed safely ({type(exc).__name__}); no complete result published.') from None


if __name__ == '__main__':
    main()
