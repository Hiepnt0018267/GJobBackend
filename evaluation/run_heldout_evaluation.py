"""Retrospective grouped threshold holdout over immutable precomputed scores."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from evaluation.benchmark_metrics import errors
from evaluation.common import EvaluationDataError, iter_csv, resolve_dataset_files
from evaluation.heldout_protocol import POLICY, bootstrap, components, evaluate, grouped_split, leakage, select_threshold
from evaluation.run_baseline_benchmark import EXPECTED_SHA, SEMANTIC_FILES, compare, load_pairs, sha

SPLIT_FIELDS = ['pair_id', 'cv_id', 'job_id', 'label', 'candidate_type', 'split', 'component_id']
TEST_FIELDS = ['pair_id', 'cv_id', 'job_id', 'human_label', 'candidate_type', 'semantic_score',
               'semantic_threshold', 'semantic_prediction', 'baseline_score', 'baseline_threshold', 'baseline_prediction', 'component_id']
ALGORITHMS = {'semantic-v1': ('semantic_score', -1., 1.), 'baseline-v1': ('baseline_score', 0., 1.)}


def now():
    return datetime.now(timezone.utc).isoformat()


def exclusive_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')


def exclusive_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)


def manifest_path(args):
    return Path(args.reports_dir) / 'heldout_split_manifest.json'


def score_inputs(args):
    if sha(args.input) != EXPECTED_SHA:
        raise EvaluationDataError('Original ground-truth hash changed.')
    originals, validation = load_pairs(args.input, args.data_dir)
    rows = {r['pair_id']: {'pair_id': r['pair_id'], 'cv_id': r['cv_id'], 'job_id': r['job_id'],
            'human_label': r['label'], 'candidate_type': r['pair_type'], 'label_reason': r['label_reason']} for r in originals}
    protected, metadata = {}, {}
    for name, folder in [('semantic-v1', args.semantic_dir), ('baseline-v1', args.baseline_dir)]:
        folder = Path(folder)
        metadata[name] = json.loads((folder / 'metrics.json').read_text())
        metrics = metadata[name]
        if metrics['reproducibility']['input_sha256'] != EXPECTED_SHA or metrics['overall']['count'] != 220:
            raise EvaluationDataError('Score benchmark provenance/size mismatch.')
        if metrics['reproducibility'].get('partial'):
            raise EvaluationDataError('Partial scores cannot be used for final holdout.')
        if name == 'semantic-v1':
            if metrics['reproducibility'].get('implementation') != 'app.services.semantic_matching_service.SemanticMatchingService.match':
                raise EvaluationDataError('Semantic algorithm identifier mismatch.')
            if metrics['reproducibility'].get('model', '').removesuffix(':latest') != 'bge-m3':
                raise EvaluationDataError('Frozen semantic model is not BGE-M3.')
            core = Path('app/services/semantic_matching_service.py')
            if sha(core) != metrics['reproducibility']['identity']['core_sha256']:
                raise EvaluationDataError('Semantic implementation changed.')
        else:
            core = Path(__file__).with_name('baseline_lexical.py')
            if metrics['definition']['version'] != 'baseline-v1-offline-lexical' or sha(core) != metrics['reproducibility']['implementation_sha256']:
                raise EvaluationDataError('Frozen lexical baseline changed.')
            if sha(Path(__file__).with_name('BASELINE_V1_FROZEN.md')) != metrics['reproducibility']['frozen_definition_sha256']:
                raise EvaluationDataError('Baseline freeze definition changed.')
        field, lower, upper = ALGORITHMS[name]
        seen = set()
        for _, prediction in iter_csv(folder / 'predictions.csv'):
            pid = prediction['pair_id']
            if pid not in rows or pid in seen:
                raise EvaluationDataError('Predictions contain missing/duplicate/unrelated pair IDs.')
            seen.add(pid)
            if any(prediction[key] != rows[pid][key] for key in ('cv_id', 'job_id', 'human_label', 'candidate_type', 'label_reason')):
                raise EvaluationDataError('Prediction ground truth differs from original.')
            score = float(prediction[field])
            if not math.isfinite(score) or not lower <= score <= upper:
                raise EvaluationDataError('Invalid frozen score.')
            if int(prediction['predicted_label']) != int(score >= metrics['overall']['threshold']):
                raise EvaluationDataError('Original prediction/default threshold mismatch.')
            rows[pid][field] = score
        if seen != set(rows):
            raise EvaluationDataError('Predictions do not cover all 220 pairs.')
        for filename in SEMANTIC_FILES:
            protected[str(folder / filename)] = sha(folder / filename)
        protected[str(core)] = sha(core)
    baseline = metadata['baseline-v1']['reproducibility']
    semantic = metadata['semantic-v1']['reproducibility']
    if baseline['source_hashes'] != semantic['source_hashes']:
        raise EvaluationDataError('Scoring source corpora differ.')
    source_files = resolve_dataset_files(args.data_dir)
    for name, digest in baseline['source_hashes'].items():
        path = source_files[name]
        if sha(path) != digest:
            raise EvaluationDataError('Current source corpus differs from frozen scores.')
        protected[str(path)] = digest
    for filename, digest in baseline['semantic_artifact_hashes'].items():
        if sha(Path(args.semantic_dir) / filename) != digest:
            raise EvaluationDataError('Semantic artifacts no longer match baseline audit.')
    protected[args.input] = EXPECTED_SHA
    for filename in ('heldout_protocol.py', 'run_heldout_evaluation.py', 'HELDOUT_PROTOCOL.md', 'benchmark_metrics.py'):
        path = Path(__file__).with_name(filename)
        protected[str(path)] = sha(path)
    return list(rows.values()), protected, validation, metadata


def verify_protected(protected):
    if any(sha(path) != digest for path, digest in protected.items()):
        raise EvaluationDataError('Protected input/algorithm/score artifact changed.')


def split_phase(args, rows, protected, validation):
    if manifest_path(args).exists() or any((Path(args.derived_dir) / f'{name}_pairs.csv').exists() for name in ('calibration', 'test')):
        raise EvaluationDataError('Split already exists; refusing split/seed search or overwrite.')
    groups = components(rows)
    print(f'Component audit: {len(groups)} components, largest {max(len(g["rows"]) for g in groups)} pairs', flush=True)
    calibration, test, audit = grouped_split(rows, args.seed)
    files = {}
    for name, partition in [('calibration', calibration), ('test', test)]:
        path = Path(args.derived_dir) / f'{name}_pairs.csv'
        records = [dict(r, label=r['human_label']) for r in partition]
        exclusive_csv(path, records, SPLIT_FIELDS); files[name] = {'path': str(path), 'sha256': sha(path)}
    manifest = {'version': POLICY['version'], 'input_sha256': EXPECTED_SHA, 'seed': args.seed,
        'policy': POLICY, 'policy_file_sha256': sha(Path(__file__).with_name('HELDOUT_PROTOCOL.md')),
        'timestamp': now(), 'validation': validation, 'protected_hashes': protected,
        'files': files, 'audit': audit,
        'assignment': {r['pair_id']: {'split': r['split'], 'component_id': r['component_id']} for r in calibration + test}}
    exclusive_json(manifest_path(args), manifest)
    report = ['# Grouped heldout split report', '', f'Input SHA-256: {EXPECTED_SHA}', f'Seed: {args.seed}',
        'Grouping: typed CV/JD connected components; no component broken.', '',
        '```json', json.dumps(audit, indent=2), '```', '',
        f'Manifest SHA-256: {sha(manifest_path(args))}', '',
        'Counts/labels/groups were used for stratification only; no scores or outcomes used.',
        'This is a retrospective partition; baseline IDF is frozen and transductive. See HELDOUT_PROTOCOL.md.']
    path = Path(args.reports_dir) / 'heldout_split_report.md'
    with path.open('x', encoding='utf-8') as handle:
        handle.write('\n'.join(report) + '\n')
    verify_protected(protected)
    print(f'Split: calibration {len(calibration)}, test {len(test)}; CV/JD/pair overlap zero', flush=True)


def read_partition(args, name, source_rows):
    manifest = json.loads(manifest_path(args).read_text())
    if manifest['seed'] != args.seed or manifest['policy'] != POLICY:
        raise EvaluationDataError('Split protocol/seed mismatch.')
    if manifest['policy_file_sha256'] != sha(Path(__file__).with_name('HELDOUT_PROTOCOL.md')):
        raise EvaluationDataError('Frozen protocol document changed.')
    verify_protected(manifest['protected_hashes'])
    by_id = {r['pair_id']: r for r in source_rows}
    subsets = {}
    for split, info in manifest['files'].items():
        if sha(info['path']) != info['sha256']:
            raise EvaluationDataError('Split CSV changed.')
        records = []
        for _, record in iter_csv(Path(info['path'])):
            pid = record['pair_id']
            if pid not in by_id or record['split'] != split or manifest['assignment'][pid] != {'split': split, 'component_id': record['component_id']}:
                raise EvaluationDataError('Partition membership/component mismatch.')
            source = by_id[pid]
            if any(record[key] != source[key] for key in ('cv_id', 'job_id', 'candidate_type')) or record['label'] != source['human_label']:
                raise EvaluationDataError('Partition changed ground truth.')
            records.append(dict(source, component_id=record['component_id'], split=split))
        subsets[split] = records
    leakage(subsets['calibration'], subsets['test'], source_rows)
    # Graph audit ensures even a forged membership mapping cannot break components.
    for group in components(subsets['calibration'] + subsets['test']):
        if len({r['split'] for r in group['rows']}) != 1:
            raise EvaluationDataError('Connected component was split.')
    return subsets[name], manifest


def calibrate_phase(args, source_rows):
    out = Path(args.output_dir)
    if (out / 'calibrated_thresholds.json').exists():
        raise EvaluationDataError('Thresholds already frozen; refusing recalibration.')
    calibration, manifest = read_partition(args, 'calibration', source_rows)
    thresholds = {}
    for name, (field, lower, upper) in ALGORITHMS.items():
        selected, sweep = select_threshold(calibration, field, lower, upper)
        thresholds[name] = {'threshold': selected['threshold'], 'score_field': field,
            'selection_metric': 'f1', 'calibration_only': True, 'selection_result': selected,
            'algorithm_identifier': 'semantic-v1' if name == 'semantic-v1' else 'baseline-v1-offline-lexical'}
        exclusive_csv(out / f'{name}_calibration_threshold_sweep.csv', sweep, list(sweep[0]))
    frozen = {'timestamp': now(), 'seed': args.seed, 'source_benchmark_sha256': EXPECTED_SHA,
        'calibration_file_sha256': manifest['files']['calibration']['sha256'],
        'test_file_sha256': manifest['files']['test']['sha256'], 'split_manifest_sha256': sha(manifest_path(args)),
        'policy': POLICY, 'protected_hashes': manifest['protected_hashes'], 'algorithms': thresholds}
    # Exclusive persist is the freeze boundary; test phase must read this file.
    exclusive_json(out / 'calibrated_thresholds.json', frozen)
    metrics = {'phase': 'calibration', 'threshold_artifact_sha256': sha(out / 'calibrated_thresholds.json'),
               'algorithms': evaluate(calibration, thresholds)}
    exclusive_json(out / 'calibration_metrics.json', metrics)
    print(json.dumps({'calibration_rows': len(calibration), 'frozen_thresholds': {k: v['threshold'] for k, v in thresholds.items()}}), flush=True)


def test_phase(args, source_rows):
    out = Path(args.output_dir)
    frozen_path = out / 'calibrated_thresholds.json'
    frozen = json.loads(frozen_path.read_text())
    test, manifest = read_partition(args, 'test', source_rows)
    if frozen['split_manifest_sha256'] != sha(manifest_path(args)) or frozen['calibration_file_sha256'] != manifest['files']['calibration']['sha256'] or frozen['test_file_sha256'] != manifest['files']['test']['sha256'] or frozen['policy'] != POLICY:
        raise EvaluationDataError('Threshold freeze/split provenance mismatch.')
    calibration_metrics = json.loads((out / 'calibration_metrics.json').read_text())
    if calibration_metrics['threshold_artifact_sha256'] != sha(frozen_path):
        raise EvaluationDataError('Frozen threshold artifact changed.')
    thresholds = frozen['algorithms']
    if set(thresholds) != set(ALGORITHMS) or any(not v['calibration_only'] or not math.isfinite(v['threshold']) or v['score_field'] != ALGORITHMS[name][0] for name, v in thresholds.items()):
        raise EvaluationDataError('Invalid calibration freeze.')
    exclusive_json(out / 'test_evaluation_started.json', {'timestamp': now(), 'threshold_sha256': sha(frozen_path),
        'test_sha256': frozen['test_file_sha256'], 'intent': 'single final evaluation, no threshold optimization'})
    # No selector invocation or test threshold sweep beyond this boundary.
    metrics = {'phase': 'test', 'timestamp': now(), 'threshold_artifact_sha256': sha(frozen_path),
        'split_manifest_sha256': sha(manifest_path(args)), 'algorithms': evaluate(test, thresholds),
        'bootstrap': bootstrap(test, thresholds, POLICY['bootstrap_resamples'], args.seed)}
    predicted = []
    for row in test:
        record = dict(row)
        for name, prefix in [('semantic-v1', 'semantic'), ('baseline-v1', 'baseline')]:
            threshold = thresholds[name]['threshold']
            record[prefix + '_threshold'] = threshold
            record[prefix + '_prediction'] = int(record[prefix + '_score'] >= threshold)
        predicted.append(record)
    exclusive_csv(out / 'test_predictions.csv', predicted, TEST_FIELDS)
    semantic, baseline = [], []
    for record in predicted:
        for target, prefix in [(semantic, 'semantic'), (baseline, 'baseline')]:
            target.append(dict(record, predicted_label=record[prefix + '_prediction']))
    stats, overlap = compare(semantic, baseline)
    exclusive_csv(out / 'test_error_overlap.csv', overlap, list(overlap[0]))
    for prefix, algorithm_rows in [('semantic', semantic), ('baseline', baseline)]:
        for kind, label in [('positives', 0), ('negatives', 1)]:
            selected = errors(algorithm_rows, label, prefix + '_score')
            fields = ['pair_id', 'cv_id', 'job_id', 'score', 'human_label', 'candidate_type', 'label_reason']
            exclusive_csv(out / f'{prefix}_false_{kind}.csv', [dict(r, score=r[prefix + '_score']) for r in selected], fields)
    metrics['paired_comparison'] = stats
    exclusive_json(out / 'test_metrics.json', metrics)
    verify_protected(frozen['protected_hashes'])
    if sha(frozen_path) != metrics['threshold_artifact_sha256']:
        raise EvaluationDataError('Threshold artifact changed during test.')
    write_report(args, manifest, frozen, calibration_metrics, metrics)
    print(json.dumps({'test_rows': len(test), 'thresholds': {k: v['threshold'] for k, v in thresholds.items()},
        'results': {k: v['overall'] for k, v in metrics['algorithms'].items()}, 'paired': stats}, indent=2), flush=True)


def write_report(args, manifest, frozen, calibration, test):
    overall = {k: v['overall'] for k, v in test['algorithms'].items()}
    table = ['| Metric | Semantic-v1 | Frozen offline lexical baseline |', '|---|---:|---:|']
    for key in ('TP', 'TN', 'FP', 'FN', 'precision', 'recall', 'f1', 'accuracy', 'specificity', 'balanced_accuracy', 'roc_auc', 'average_precision'):
        table.append(f"| {key} | {overall['semantic-v1'][key]} | {overall['baseline-v1'][key]} |")
    sections = [('1. Objective', 'Grouped calibration/test separation for threshold selection on frozen scores, not an external blind validation.'),
        ('2. Ground Truth', f'{EXPECTED_SHA}; 220 original human decisions, unchanged. Sampling groups are not labels.'),
        ('3. Split Method', 'Typed bipartite CV/JD graph; whole connected components. Fixed greedy + improving flips/swaps using counts only; seed42.'),
        ('4. Split Statistics', json.dumps(manifest['audit'], indent=2)),
        ('5. Leakage Verification', 'Shared CV=0, shared JD=0, shared pair=0; all220 exactly once; component membership/labels verified.'),
        ('6. Algorithms Frozen', 'Semantic-v1: unchanged BGE-M3 raw cosine. Baseline-v1-offline-lexical: unchanged 0.7 TF-IDF lexical cosine + 0.3 title coverage. Original scores/artifacts unchanged; no IDF refit/provider call.'),
        ('7. Calibration Threshold Selection', POLICY['selection'] + '. Candidates from calibration only; score >= threshold.'),
        ('8. Calibrated Thresholds', json.dumps({k: v['threshold'] for k, v in frozen['algorithms'].items()}, indent=2)),
        ('9. Calibration Results', json.dumps(calibration['algorithms'], indent=2)),
        ('10. Held-out Test Results', '\n'.join(table)),
        ('11. Hard Negative Held-out Results', json.dumps({k: v['groups']['HARD_NEGATIVE_CANDIDATE'] for k, v in test['algorithms'].items()}, indent=2)),
        ('12. Easy Negative Held-out Results', json.dumps({k: v['groups']['EASY_NEGATIVE_CANDIDATE'] for k, v in test['algorithms'].items()}, indent=2)),
        ('13. Positive Candidate Held-out Results', json.dumps({k: v['groups']['POSITIVE_CANDIDATE'] for k, v in test['algorithms'].items()}, indent=2)),
        ('14. Error Overlap', json.dumps(test['paired_comparison'], indent=2)),
        ('15. False Positive Analysis', 'Test-only FP CSVs use fixed thresholds, sorted highest score first. Human reasons are diagnostic only.'),
        ('16. False Negative Analysis', 'Test-only FN CSVs sorted lowest score first. No annotation revision or post-test tuning.'),
        ('17. Ranking vs Classification', 'ROC-AUC/AP use continuous test scores; classification uses calibration-frozen thresholds. Easy groups cannot establish hard-case superiority.'),
        ('18. Confidence / Uncertainty', json.dumps(test['bootstrap'], indent=2)),
        ('19. Algorithm Selection Assessment', 'Interpret measured test tradeoffs and uncertainty; no automatic winner or production switch. Retrospective/transductive limitations prevent confirmatory deployment claims.'),
        ('20. Recommended Next Step', 'Collect genuinely unseen independent labels and calibrate/evaluate frozen models on grouped data. No hybrid or next-step implementation here.')]
    text = '# Held-out Semantic-v1 vs Baseline-v1\n\n' + '\n\n'.join(f'## {heading}\n\n{body}' for heading, body in sections)
    text += '\n\n## Critical validity limitations\n\n' + '\n'.join(POLICY['limitations'])
    text += '\nSingle reviewer; difficulty-focused small sample; shared-entity test rows; no representative prevalence/per-job ranking pool; extraction quality not evaluated.\n'
    with (Path(args.output_dir) / 'final_comparison.md').open('x', encoding='utf-8') as handle:
        handle.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['split', 'calibrate', 'test', 'all'], default='all')
    parser.add_argument('--input', default='evaluation/data/derived/evaluation_pairs_labeled.csv')
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--derived-dir', default='evaluation/data/derived')
    parser.add_argument('--reports-dir', default='evaluation/reports')
    parser.add_argument('--output-dir', default='evaluation/results/heldout')
    parser.add_argument('--semantic-dir', default='evaluation/results/semantic-v1')
    parser.add_argument('--baseline-dir', default='evaluation/results/baseline-v1')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args(argv)
    if args.seed != POLICY['seed']:
        parser.error('Real protocol freezes seed42; no split/seed search.')
    if Path(args.output_dir).resolve() in {Path(args.semantic_dir).resolve(), Path(args.baseline_dir).resolve()}:
        parser.error('Heldout output must be separate from protected score directories.')
    try:
        rows, protected, validation, _ = score_inputs(args)
        if args.phase in ('split', 'all'):
            split_phase(args, rows, protected, validation)
        if args.phase in ('calibrate', 'all'):
            calibrate_phase(args, rows)
        if args.phase in ('test', 'all'):
            test_phase(args, rows)
    except (EvaluationDataError, FileExistsError) as exc:
        parser.exit(1, f'Heldout stopped safely: {exc}\n')


if __name__ == '__main__':
    main()
