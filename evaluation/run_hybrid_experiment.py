"""Offline Hybrid-v1: calibration-only fit, then two explicitly consumed diagnostics."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from evaluation.benchmark_metrics import errors
from evaluation.common import EvaluationDataError, iter_csv
from evaluation.hybrid_protocol import POLICY, apply_config, bootstrap_hybrid, calibrate, error_overlap, summarize
from evaluation.run_heldout_evaluation import exclusive_csv, exclusive_json, read_partition, score_inputs, sha, verify_protected

FIELDS = ['pair_id', 'cv_id', 'job_id', 'human_label', 'candidate_type', 'semantic_score',
          'semantic_normalized', 'semantic_prediction', 'baseline_score', 'baseline_normalized',
          'baseline_prediction', 'hybrid_score', 'hybrid_threshold', 'hybrid_prediction']


def component_thresholds():
    path = Path('evaluation/results/heldout/calibrated_thresholds.json')
    if sha(path) != '5d552274da24d355c1c9eb631377ace6d31fe059b2a3477434d9ae8644e746f8':
        raise EvaluationDataError('Original component thresholds changed.')
    return json.loads(path.read_text())['algorithms']


def old_scores(args):
    # Old220 only. Does not open70 labels/scores or import any provider.
    proxy = argparse.Namespace(input='evaluation/data/derived/evaluation_pairs_labeled.csv',
        data_dir=args.data_dir, semantic_dir='evaluation/results/semantic-v1',
        baseline_dir='evaluation/results/baseline-v1', reports_dir='evaluation/reports', seed=42)
    rows, protected, _, _ = score_inputs(proxy)
    return rows, protected, proxy


def calibrate_phase(args):
    out = Path(args.output_dir)
    if (out / 'hybrid_config.json').exists():
        raise EvaluationDataError('Hybrid config already frozen; no recalibration.')
    rows, protected, proxy = old_scores(args)
    calibration, manifest = read_partition(proxy, 'calibration', rows)
    if len(calibration) != 132:
        raise EvaluationDataError('Expected132 calibration pairs.')
    config, selection = calibrate(calibration)
    thresholds = component_thresholds()
    normalized = apply_config(calibration, config)
    comparison, _ = summarize(normalized, config, thresholds)
    for filename in ('hybrid_protocol.py', 'run_hybrid_experiment.py', 'HYBRID_V1_PROTOCOL.md'):
        path = Path(__file__).with_name(filename); protected[str(path)] = sha(path)
    for name in ('heldout_split_manifest.json',):
        path = Path('evaluation/reports') / name; protected[str(path)] = sha(path)
    for name in ('calibration_pairs.csv', 'test_pairs.csv'):
        path = Path('evaluation/data/derived') / name; protected[str(path)] = sha(path)
    path = Path('evaluation/results/heldout/calibrated_thresholds.json'); protected[str(path)] = sha(path)
    state_path = Path('evaluation/cache/fresh-test/baseline_development_state.json')
    if sha(state_path) != '7b1405dc50bf26e96517b2ff2fdda65e8a1dddab1e7069e6ac44863ce8dbb25d':
        raise EvaluationDataError('Frozen development-only IDF state changed.')
    protected[str(state_path)] = sha(state_path)
    config.update(timestamp=datetime.now(timezone.utc).isoformat(), calibration_pair_count=132,
        calibration_hash=manifest['files']['calibration']['sha256'], seed=42,
        semantic_version='semantic-v1', baseline_version='baseline-v1-offline-lexical',
        component_thresholds=thresholds, source_score_artifact_hashes=protected,
        fit_scope='task14b4_calibration_only', frozen=True)
    verify_protected(protected)
    exclusive_json(out / 'hybrid_config.json', config)  # freeze boundary
    exclusive_json(out / 'calibration_results.json', {'selection': selection, 'comparison': comparison,
        'config_sha256': sha(out / 'hybrid_config.json')})
    for alternative in selection['alternatives']:
        sweep = alternative['sweep']
        exclusive_csv(out / f'calibration_alpha_{alternative["alpha"]:.2f}_sweep.csv', sweep, list(sweep[0]))
    print(json.dumps({'selected': selection['selected'], 'alpha': config['alpha'],
        'fallback_triggered': config['fallback_triggered'], 'config_sha256': sha(out / 'hybrid_config.json')}), flush=True)


def read_config(args):
    out = Path(args.output_dir)
    config = json.loads((out / 'hybrid_config.json').read_text())
    calibration = json.loads((out / 'calibration_results.json').read_text())
    if calibration['config_sha256'] != sha(out / 'hybrid_config.json') or config['policy'] != POLICY or not config['frozen']:
        raise EvaluationDataError('Hybrid freeze changed.')
    verify_protected(config['source_score_artifact_hashes'])
    if config['component_thresholds'] != component_thresholds():
        raise EvaluationDataError('Component thresholds changed.')
    return config


def evaluate_rows(rows, config):
    normalized = apply_config(rows, config)
    metrics, thresholds = summarize(normalized, config, config['component_thresholds'])
    overlap, complementarity = error_overlap(normalized, thresholds)
    metrics['error_complementarity'] = complementarity
    return overlap, metrics, thresholds


def heldout_phase(args):
    out = Path(args.output_dir)
    config = read_config(args)
    rows, _, proxy = old_scores(args)
    heldout, _ = read_partition(proxy, 'test', rows)
    if len(heldout) != 88:
        raise EvaluationDataError('Expected88 retrospective development holdout pairs.')
    exclusive_json(out / 'heldout_started.json', {'config_sha256': sha(out / 'hybrid_config.json'),
        'timestamp': datetime.now(timezone.utc).isoformat(), 'status': 'consumed development holdout, once'})
    predictions, metrics, thresholds = evaluate_rows(heldout, config)
    metrics.update(dataset_status='RETROSPECTIVE DEVELOPMENT HOLDOUT, NOT INDEPENDENT',
        config_sha256=sha(out / 'hybrid_config.json'))
    for row in predictions:
        row['hybrid_threshold'] = config['threshold']
    exclusive_csv(out / 'heldout_predictions.csv', predictions, FIELDS)
    exclusive_csv(out / 'heldout_error_overlap.csv', predictions,
        FIELDS + ['component_bucket', 'hybrid_correct'])
    view = [dict(row, predicted_label=row['hybrid_prediction']) for row in predictions]
    for name, label in [('positives', 0), ('negatives', 1)]:
        exclusive_csv(out / f'heldout_false_{name}.csv', errors(view, label, 'hybrid_score'),
            ['pair_id', 'cv_id', 'job_id', 'human_label', 'candidate_type', 'hybrid_score', 'label_reason'])
    uncertainty = bootstrap_hybrid(predictions, thresholds)
    exclusive_json(out / 'bootstrap.json', uncertainty)
    exclusive_json(out / 'heldout_metrics.json', metrics)
    verify_protected(config['source_score_artifact_hashes'])
    print(json.dumps({'heldout': metrics['hybrid-v1']['overall'], 'tradeoffs': metrics['tradeoffs'],
        'floor_met': metrics['hybrid_recall_floor_on_this_split']}, indent=2), flush=True)


def fresh_phase(args):
    out = Path(args.output_dir)
    config = read_config(args)
    heldout = json.loads((out / 'heldout_metrics.json').read_text())
    if heldout['config_sha256'] != sha(out / 'hybrid_config.json'):
        raise EvaluationDataError('88 phase must finish with the same frozen config first.')
    fresh_dir = Path('evaluation/results/fresh-test')
    freeze = json.loads((fresh_dir / 'fresh_ground_truth_frozen.json').read_text())
    verify_protected(freeze['protected_hashes'])
    if sha(freeze['idf_state_path']) != freeze['idf_state_sha256']:
        raise EvaluationDataError('Frozen development-only IDF state changed.')
    labels = {r['pair_id']: r for _, r in iter_csv(Path(freeze['input_path']))}
    rows = []
    seen = set()
    for _, row in iter_csv(fresh_dir / 'predictions.csv'):
        pid = row['pair_id']
        if pid not in labels or pid in seen or any(row[key] != labels[pid][source] for key, source in (
                ('cv_id', 'cv_id'), ('job_id', 'job_id'), ('human_label', 'label'), ('candidate_type', 'pair_type'))):
            raise EvaluationDataError('Consumed fresh scores/ground truth do not align.')
        seen.add(pid)
        rows.append(dict(row, semantic_score=float(row['semantic_score']), baseline_score=float(row['baseline_score']),
            label_reason=labels[pid]['label_reason']))
    if len(rows) != 70 or seen != set(labels):
        raise EvaluationDataError('Consumed fresh diagnostic requires all70 pairs.')
    original_hashes = {str(p): sha(p) for p in fresh_dir.iterdir() if p.is_file()}
    exclusive_json(out / 'fresh_diagnostic_started.json', {'timestamp': datetime.now(timezone.utc).isoformat(),
        'config_sha256': sha(out / 'hybrid_config.json'), 'status': 'POST-HOC CONSUMED FRESH-SET DIAGNOSTIC, NOT INDEPENDENT HYBRID VALIDATION',
        'fresh_artifact_hashes': original_hashes})
    predictions, metrics, _ = evaluate_rows(rows, config)
    metrics.update(dataset_status='POST-HOC CONSUMED FRESH-SET DIAGNOSTIC; NOT INDEPENDENT HYBRID VALIDATION',
        config_sha256=sha(out / 'hybrid_config.json'), frozen_idf_state_sha256=freeze['idf_state_sha256'])
    for row in predictions:
        row['hybrid_threshold'] = config['threshold']
    exclusive_csv(out / 'fresh_diagnostic_predictions.csv', predictions, FIELDS)
    exclusive_csv(out / 'fresh_diagnostic_error_overlap.csv', predictions, FIELDS + ['component_bucket', 'hybrid_correct'])
    exclusive_json(out / 'fresh_diagnostic_metrics.json', metrics)
    verify_protected(original_hashes)
    verify_protected(config['source_score_artifact_hashes'])
    print(json.dumps({'consumed_fresh_diagnostic': metrics['hybrid-v1']['overall'],
                     'warning': metrics['dataset_status']}, indent=2), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['calibrate', 'heldout', 'fresh', 'all'], default='all')
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--output-dir', default='evaluation/results/hybrid-v1')
    args = parser.parse_args(argv)
    if Path(args.output_dir).resolve() in {Path('evaluation/results/' + name).resolve() for name in ('semantic-v1', 'baseline-v1', 'heldout', 'fresh-test')}:
        parser.error('Hybrid artifacts must not modify old result directories.')
    try:
        if args.phase in ('calibrate', 'all'):
            calibrate_phase(args)
        if args.phase in ('heldout', 'all'):
            heldout_phase(args)
        if args.phase in ('fresh', 'all'):
            fresh_phase(args)
    except (EvaluationDataError, FileExistsError) as exc:
        parser.exit(1, f'Hybrid stopped safely: {exc}\n')


if __name__ == '__main__':
    main()
