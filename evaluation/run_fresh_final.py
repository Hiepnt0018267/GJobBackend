"""Phase B: freeze human truth and development state, then one fixed-threshold evaluation."""
import argparse
import asyncio
import csv
import hashlib
import json
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

from evaluation.benchmark_metrics import errors
from evaluation.common import EvaluationDataError, iter_csv
from evaluation.fresh_final_state import development_state, transform_only
from evaluation.fresh_test_protocol import exclusion_files, validate_fresh_labels
from evaluation.heldout_protocol import bootstrap, evaluate
from evaluation.run_baseline_benchmark import compare, sources
from evaluation.run_heldout_evaluation import TEST_FIELDS, exclusive_csv, exclusive_json, verify_protected


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validated_truth(args):
    original = Path(args.old_benchmark)
    label_path = Path(args.input)
    with tempfile.TemporaryDirectory(prefix='fresh-truth-validate-') as temporary:
        validation = validate_fresh_labels(label_path, Path(temporary) / 'validated.csv', data_dir=Path(args.data_dir),
            old_benchmark=original, min_rows=70, max_rows=70)
    rows = [r for _, r in iter_csv(label_path)]
    seed_rows = [r for _, r in iter_csv(Path(args.seed))]
    by_seed = {r['pair_id']: r for r in seed_rows}
    progress = {r['pair_id']: r for _, r in iter_csv(Path(args.progress))}
    if {r['pair_id'] for r in rows} != {r['pair_id'] for r in seed_rows} or len(progress) != 70:
        raise EvaluationDataError('Fresh human truth/seed/progress membership differs.')
    for row in rows:
        if any(row[key] != by_seed[row['pair_id']][key] for key in ('cv_id', 'job_id', 'pair_type', 'cv_source_row', 'job_source_row')):
            raise EvaluationDataError('Fresh export changed seed membership/source/sampling metadata.')
        human = progress[row['pair_id']]
        if human['review_status'] != 'REVIEWED' or not human['reviewed_at'] or human['human_label'] != row['label'] or human['human_reason'] != row['label_reason']:
            raise EvaluationDataError('Fresh truth is not fully human-confirmed.')
    rows.sort(key=lambda r: r['pair_id'])
    return rows, validation, sum(bool(r['ai_reason']) for r in progress.values())


def freeze(args):
    out = Path(args.output_dir)
    if (out / 'fresh_ground_truth_frozen.json').exists():
        raise EvaluationDataError('Fresh truth already frozen; refusing refreeze.')
    rows, validation, assisted = validated_truth(args)
    prior = json.loads(Path(args.thresholds).read_text())
    verify_protected(prior['protected_hashes'])
    if sha(args.thresholds) != '5d552274da24d355c1c9eb631377ace6d31fe059b2a3477434d9ae8644e746f8':
        raise EvaluationDataError('Task14B.4 threshold artifact changed.')
    old_rows = [r for _, r in iter_csv(Path(args.old_benchmark))]
    cvs, jobs, _ = sources(old_rows, Path(args.data_dir))
    documents = {f'cv:{key}': value for key, value in cvs.items()} | {f'job:{key}': value['text'] for key, value in jobs.items()}
    engine, state = development_state(documents)
    stored = {r['pair_id']: r for _, r in iter_csv(Path('evaluation/results/baseline-v1/predictions.csv'))}
    for row in old_rows:
        value = engine.score('cv:' + row['cv_id'], 'job:' + row['job_id'], jobs[row['job_id']]['title'])
        if value != float(stored[row['pair_id']]['baseline_score']):
            raise EvaluationDataError('Development IDF reconstruction does not reproduce frozen scores.')
    state.update(implementation_sha256=sha('evaluation/baseline_lexical.py'),
                 development_benchmark_sha256=sha(args.old_benchmark), development_scores_reproduced=220)
    state_path = Path(args.cache_dir) / 'baseline_development_state.json'
    exclusive_json(state_path, state)  # hashed vocabulary only, private gitignored cache
    protected = dict(prior['protected_hashes'])
    for path in [args.input, args.seed, args.progress, args.thresholds, *map(str, exclusion_files(args.old_benchmark)),
                 'evaluation/fresh_final_state.py', 'evaluation/run_fresh_final.py']:
        protected[str(path)] = sha(path)
    record = {'timestamp': datetime.now(timezone.utc).isoformat(), 'phase': 'frozen-before-fresh-scoring',
        'input_path': str(Path(args.input).resolve()), 'input_sha256': sha(args.input), 'validation': validation,
        'human_confirmed': 70, 'qwen_assisted_pairs': assisted,
        'overlaps': {'old_cv': 0, 'old_jd': 0, 'historical_cv': 0, 'historical_jd': 0, 'old_pair': 0},
        'threshold_artifact_sha256': sha(args.thresholds), 'algorithms': prior['algorithms'],
        'idf_state_path': str(state_path), 'idf_state_sha256': sha(state_path),
        'idf_protocol': 'Reconstructed from old382 development texts only; fixed vocabulary inference; no fresh fit.',
        'idf_transform_policy': state['oov_policy'], 'protected_hashes': protected}
    exclusive_json(out / 'fresh_ground_truth_frozen.json', record)
    print(json.dumps({'frozen_ground_truth': record['input_path'], 'validation': validation,
        'sha256': record['input_sha256'], 'development_documents': len(documents), 'old_scores_reproduced': 220}), flush=True)


async def scoring(args):
    from evaluation.run_semantic_benchmark import CachedVectors, context_provider, prepare_sources, score_pairs
    out = Path(args.output_dir)
    frozen = json.loads((out / 'fresh_ground_truth_frozen.json').read_text())
    verify_protected(frozen['protected_hashes'])
    if sha(frozen['idf_state_path']) != frozen['idf_state_sha256']:
        raise EvaluationDataError('Frozen development IDF state changed.')
    rows, _, _ = validated_truth(args)
    if sha(args.input) != frozen['input_sha256']:
        raise EvaluationDataError('Fresh labels changed after freeze.')
    exclusive_json(out / 'evaluation_started.json', {'timestamp': datetime.now(timezone.utc).isoformat(),
        'ground_truth_freeze_sha256': sha(out / 'fresh_ground_truth_frozen.json'), 'intent': 'one fresh evaluation; no calibration'})
    meta = json.loads(Path('evaluation/results/semantic-v1/metrics.json').read_text())
    identity = meta['reproducibility']['identity']
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(identity['base_url'].rstrip('/') + '/api/tags')
        response.raise_for_status()
        matches = [m for m in response.json()['models'] if m['name'] == identity['model'] and m['digest'] == identity['digest']]
    if len(matches) != 1:
        raise EvaluationDataError('Frozen BGE-M3 model digest unavailable/changed.')
    cvs, jobs, _ = prepare_sources(rows, Path(args.data_dir))
    cache = CachedVectors(context_provider(identity['base_url'], meta['reproducibility']['model'], 30,
        identity['num_ctx'], identity['num_batch']), Path(args.cache_dir) / 'embeddings', identity)
    await cache.preload(cvs, jobs, 4)
    thresholds = frozen['algorithms']
    semantic = await score_pairs(rows, cvs, jobs, cache, thresholds['semantic-v1']['threshold'])
    raw_cvs, raw_jobs, _ = sources(rows, Path(args.data_dir))
    fresh_documents = {f'cv:{key}': text for key, text in raw_cvs.items()} | {f'job:{key}': job['text'] for key, job in raw_jobs.items()}
    state = json.loads(Path(frozen['idf_state_path']).read_text())
    engine = transform_only(state, fresh_documents)
    baseline = []
    for row in rows:
        value = engine.score('cv:' + row['cv_id'], 'job:' + row['job_id'], raw_jobs[row['job_id']]['title'])
        baseline.append(dict(pair_id=row['pair_id'], cv_id=row['cv_id'], job_id=row['job_id'], human_label=row['label'],
            candidate_type=row['pair_type'], label_reason=row['label_reason'], baseline_score=value,
            predicted_label=int(value >= thresholds['baseline-v1']['threshold'])))
    joined = []
    by_semantic = {r['pair_id']: r for r in semantic}
    for row in baseline:
        other = by_semantic[row['pair_id']]
        joined.append(dict(row, semantic_score=other['semantic_score'], semantic_prediction=other['predicted_label'],
            baseline_prediction=row['predicted_label'], semantic_threshold=thresholds['semantic-v1']['threshold'],
            baseline_threshold=thresholds['baseline-v1']['threshold']))
    results = evaluate(joined, thresholds)
    stats, overlap = compare(semantic, baseline)
    uncertainty = bootstrap(joined, thresholds, 1000, 42)
    verify_protected(frozen['protected_hashes'])
    if sha(frozen['idf_state_path']) != frozen['idf_state_sha256']:
        raise EvaluationDataError('Fitting state mutated during evaluation.')
    exclusive_csv(out / 'predictions.csv', joined, [field for field in TEST_FIELDS if field != 'component_id'])
    exclusive_csv(out / 'error_overlap.csv', overlap, list(overlap[0]))
    for prefix, data in [('semantic', semantic), ('baseline', baseline)]:
        for suffix, label in [('positives', 0), ('negatives', 1)]:
            selected = errors(data, label, prefix + '_score')
            exclusive_csv(out / f'{prefix}_false_{suffix}.csv', [dict(r, score=r[prefix + '_score']) for r in selected],
                ['pair_id', 'cv_id', 'job_id', 'score', 'human_label', 'candidate_type', 'label_reason'])
    metrics = {'validation': frozen['validation'], 'input_sha256': frozen['input_sha256'],
        'algorithms': results, 'paired_comparison': stats, 'thresholds': {k: v['threshold'] for k, v in thresholds.items()},
        'idf_state_sha256': frozen['idf_state_sha256'], 'idf_protocol': frozen['idf_protocol'],
        'cache_hits': cache.hits, 'cache_misses': cache.misses, 'fresh_scoring_count': len(joined)}
    exclusive_json(out / 'metrics.json', metrics)
    exclusive_json(out / 'bootstrap.json', uncertainty)
    print(json.dumps({'metrics': {name: values['overall'] for name, values in results.items()}, 'paired': stats,
        'f1_delta_ci': uncertainty['paired_f1_delta_baseline_minus_semantic']}, indent=2), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['freeze', 'evaluate', 'all'], default='all')
    parser.add_argument('--input', default='evaluation/data/derived/fresh_test_pairs_labeled.csv')
    parser.add_argument('--seed', default='evaluation/data/derived/fresh_test_pairs_seed.csv')
    parser.add_argument('--progress', default='evaluation/data/derived/evaluation_labeling_progress_fresh_test_pairs_seed.csv')
    parser.add_argument('--old-benchmark', default='evaluation/data/derived/evaluation_pairs_labeled.csv')
    parser.add_argument('--thresholds', default='evaluation/results/heldout/calibrated_thresholds.json')
    parser.add_argument('--output-dir', default='evaluation/results/fresh-test')
    parser.add_argument('--cache-dir', default='evaluation/cache/fresh-test')
    parser.add_argument('--data-dir', required=True)
    args = parser.parse_args(argv)
    if Path(args.output_dir).resolve() in {Path(path).resolve() for path in (
            'evaluation/results/semantic-v1', 'evaluation/results/baseline-v1', 'evaluation/results/heldout')}:
        parser.error('Fresh results cannot modify historical benchmark directories.')
    try:
        if args.phase in ('freeze', 'all'):
            freeze(args)
        if args.phase in ('evaluate', 'all'):
            asyncio.run(scoring(args))
    except Exception as exc:
        # No raw provider body, CV/JD or credential details in error output.
        raise SystemExit(f'Fresh final stopped safely ({type(exc).__name__}); no retuning/retry evaluation.') from None


if __name__ == '__main__':
    main()
