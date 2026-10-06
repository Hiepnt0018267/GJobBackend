"""Offline frozen lexical baseline; no app/provider/DB imports or network calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from evaluation.baseline_lexical import DEFAULT_THRESHOLD, LexicalBaseline, definition
from evaluation.benchmark_metrics import analyze, errors, threshold_analysis
from evaluation.common import EvaluationDataError, PAIR_TYPES, iter_csv, resolve_dataset_files
from evaluation.labeling_store import atomic_csv
from evaluation.validate_labels import validate_labeled_file

EXPECTED_SHA = '28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8'
FIELDS = ['pair_id', 'cv_id', 'job_id', 'human_label', 'baseline_score', 'predicted_label', 'candidate_type', 'label_reason']
SEMANTIC_FILES = ['report.md', 'metrics.json', 'predictions.csv', 'threshold_analysis.csv',
                  'false_positives.csv', 'false_negatives.csv', 'hard_negative_errors.csv']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_pairs(path, data_dir, count=220):
    with tempfile.TemporaryDirectory(prefix='gjob-baseline-validate-') as temporary:
        summary = validate_labeled_file(path, Path(temporary) / 'validated.csv', data_dir=data_dir)
    if summary['rows'] != count:
        raise EvaluationDataError(f'Expected {count} pairs, got {summary["rows"]}.')
    return sorted((r for _, r in iter_csv(Path(path))), key=lambda r: r['pair_id']), summary


def sources(rows, data_dir):
    files = resolve_dataset_files(data_dir)
    cvs, jobs = {}, {}
    cv_ids, job_ids = {r['cv_id'] for r in rows}, {r['job_id'] for r in rows}
    for _, raw in iter_csv(files['Resume.csv']):
        cid = raw['ID'].strip()
        if cid in cv_ids:
            if cid in cvs:
                raise EvaluationDataError('Duplicate CV source reference.')
            cvs[cid] = raw['Resume_str']
    for _, raw in iter_csv(files['job_postings.csv']):
        jid = raw['job_id'].strip()
        if jid in job_ids:
            if jid in jobs:
                raise EvaluationDataError('Duplicate JD source reference.')
            jobs[jid] = {'title': raw['title'], 'text': '\n\n'.join(raw.get(field, '') for field in ('title', 'description', 'skills_desc'))}
    if set(cvs) != cv_ids or set(jobs) != job_ids or any(not t.strip() for t in cvs.values()):
        raise EvaluationDataError('Source IDs/text missing.')
    return cvs, jobs, files


def predict(rows, cvs, jobs, threshold):
    documents = {f'cv:{key}': text for key, text in cvs.items()} | {f'job:{key}': job['text'] for key, job in jobs.items()}
    engine = LexicalBaseline(documents)
    output = []
    for row in sorted(rows, key=lambda r: r['pair_id']):
        try:
            value = engine.score('cv:' + row['cv_id'], 'job:' + row['job_id'], jobs[row['job_id']]['title'])
        except (KeyError, ValueError) as exc:
            raise EvaluationDataError(f'Cannot score pair {row["pair_id"]} ({type(exc).__name__}).') from None
        # Human and sampling metadata are attached only AFTER the source-only score.
        output.append(dict(pair_id=row['pair_id'], cv_id=row['cv_id'], job_id=row['job_id'], human_label=row['label'],
            baseline_score=value, predicted_label=int(value >= threshold), candidate_type=row['pair_type'], label_reason=row['label_reason']))
    return output


def summarize(rows, threshold):
    thresholds, best = threshold_analysis(rows, threshold, 'baseline_score')
    return dict(overall=analyze(rows, threshold, 'baseline_score'),
        groups={kind: analyze([r for r in rows if r['candidate_type'] == kind], threshold, 'baseline_score') for kind in PAIR_TYPES},
        best_exploratory_f1_threshold=best,
        threshold_warning='This is an in-sample exploratory threshold estimate, not a held-out production calibration.'), thresholds


def compare(semantic, baseline):
    by_id = {r['pair_id']: r for r in semantic}
    if len(by_id) != len(semantic) or set(by_id) != {r['pair_id'] for r in baseline}:
        raise EvaluationDataError('Semantic/baseline pair sets differ.')
    overlap = []
    for row in sorted(baseline, key=lambda r: r['pair_id']):
        other = by_id[row['pair_id']]
        if any(str(row[k]) != str(other[k]) for k in ('cv_id', 'job_id', 'human_label', 'candidate_type', 'label_reason')):
            raise EvaluationDataError('Semantic/baseline ground truth or references differ.')
        scorrect = int(other['predicted_label']) == int(row['human_label'])
        bcorrect = int(row['predicted_label']) == int(row['human_label'])
        bucket = {(True, True): 'BOTH_CORRECT', (False, False): 'BOTH_WRONG',
                  (True, False): 'SEMANTIC_ONLY_CORRECT', (False, True): 'BASELINE_ONLY_CORRECT'}[scorrect, bcorrect]
        overlap.append(dict(pair_id=row['pair_id'], human_label=row['human_label'], semantic_score=float(other['semantic_score']),
            semantic_prediction=int(other['predicted_label']), baseline_score=row['baseline_score'],
            baseline_prediction=row['predicted_label'], candidate_type=row['candidate_type'], outcome_bucket=bucket))
    hard = [r for r in overlap if r['candidate_type'] == 'HARD_NEGATIVE_CANDIDATE' and r['human_label'] == '0']
    stats = dict(human_negatives=len(hard), semantic_fp=sum(r['semantic_prediction'] == 1 for r in hard),
        baseline_fp=sum(r['baseline_prediction'] == 1 for r in hard),
        both_fp=sum(r['semantic_prediction'] == r['baseline_prediction'] == 1 for r in hard),
        semantic_only_fp=sum(r['semantic_prediction'] == 1 and r['baseline_prediction'] == 0 for r in hard),
        baseline_only_fp=sum(r['semantic_prediction'] == 0 and r['baseline_prediction'] == 1 for r in hard))
    return dict(error_overlap=dict(Counter(r['outcome_bucket'] for r in overlap)), hard_negative_head_to_head=stats), overlap


def table_metrics(semantic, baseline):
    lines = ['| Metric | Semantic-v1 | Offline lexical baseline |', '|---|---:|---:|']
    for key in ('threshold', 'TP', 'TN', 'FP', 'FN', 'precision', 'recall', 'f1', 'accuracy', 'specificity', 'roc_auc', 'average_precision'):
        lines.append(f'| {key} | {semantic.get(key)} | {baseline.get(key)} |')
    return lines


def write_results(out, rows, metrics, thresholds):
    out.mkdir(parents=True, exist_ok=True)
    atomic_csv(out / 'predictions.csv', rows, FIELDS)
    atomic_csv(out / 'threshold_analysis.csv', thresholds, list(thresholds[0]))
    for name, selection in [('false_positives.csv', errors(rows, 0, 'baseline_score')),
            ('false_negatives.csv', errors(rows, 1, 'baseline_score')),
            ('hard_negative_errors.csv', sorted((r for r in rows if r['candidate_type'] == 'HARD_NEGATIVE_CANDIDATE' and r['human_label'] == '0'), key=lambda r: (-r['baseline_score'], r['pair_id'])))]:
        atomic_csv(out / name, selection, FIELDS)
    (out / 'metrics.json').write_text(json.dumps(metrics, indent=2, allow_nan=False), encoding='utf-8')
    sections = [('1. Objective', 'Measure a frozen offline lexical reference on the same 220 human-labeled pairs.'),
        ('2. Ground Truth', 'Only human label/label_reason; sampling groups are not labels. Input validated and hashed.'),
        ('3. Baseline Definition', 'baseline-v1-offline-lexical, NOT the existing structured-skill production engine. See BASELINE_V1_FROZEN.md.'),
        ('4. Preprocessing', 'NFKC/casefold, email/URL removal, punctuation-aware tokens, frozen local stopwords. No skills/seniority inference.'),
        ('5. Exact Scoring Formula', json.dumps(metrics['definition'], indent=2)),
        ('6. Default Threshold', '0.5, frozen before real run; evaluation assumption, not production calibration.'),
        ('7. Main Results', json.dumps(metrics['overall'], indent=2)),
        ('8. Confusion Matrix', json.dumps({k: metrics['overall'][k] for k in ('TP', 'TN', 'FP', 'FN')})),
        ('9. Score Distribution', json.dumps({k: metrics['overall'][k] for k in ('positive_scores', 'negative_scores')}, indent=2)),
        ('10. Threshold Analysis', metrics['threshold_warning'] + '\n' + json.dumps(metrics['best_exploratory_f1_threshold'])),
        ('11. Candidate Group Analysis', json.dumps(metrics['groups'], indent=2)),
        ('12. Hard Negative Analysis', 'FPR denominator is human negatives, not all hard-group candidates. hard_negative_errors.csv lists all human negatives highest score first.'),
        ('13. False Positives', 'false_positives.csv, highest score first; source IDs and allowed human reasons only.'),
        ('14. False Negatives', 'false_negatives.csv, lowest score first; no labels changed.'),
        ('15. Limitations', '220 difficulty-focused, single-reviewer pairs; intentionally simple baseline; no held-out calibration; raw extraction not evaluated; no hybrid. IDF fitted transductively on this corpus; title tokens may be generic. Incidental source terms can affect lexical score. Not the production skill matcher.'),
        ('16. Reproducibility', json.dumps(metrics['reproducibility'], indent=2)),
        ('17. Conclusion', 'Interpret with comparison report; no production algorithm switch, no post-hoc tuning.')]
    (out / 'report.md').write_text('# Baseline-v1 Benchmark\n\n' + '\n\n'.join(f'## {heading}\n\n{body}' for heading, body in sections) + '\n', encoding='utf-8')


def write_comparison(out, semantic, baseline, stats, overlap):
    out.mkdir(parents=True, exist_ok=True)
    atomic_csv(out / 'error_overlap.csv', overlap, list(overlap[0]))
    combined = dict(stats, semantic_default=semantic['overall'], baseline_default=baseline['overall'],
        semantic_groups=semantic['groups'], baseline_groups=baseline['groups'],
        semantic_best_in_sample=semantic['best_exploratory_f1_threshold'], baseline_best_in_sample=baseline['best_exploratory_f1_threshold'])
    (out / 'semantic_vs_baseline.json').write_text(json.dumps(combined, indent=2, allow_nan=False), encoding='utf-8')
    lines = ['# Semantic-v1 vs Baseline-v1', '', '## 1. Evaluation Setup', '',
        'Same input hash, all 220 source-linked human decisions; same metric/tie/threshold-exploration policy. Candidate groups are not labels.', '',
        '## 2. Algorithms', '', 'Semantic: existing BGE-M3 raw-text cosine. Baseline: frozen offline TF-IDF/title reference, not production structured-skill coverage.', '',
        '## 3. Default Threshold Comparison', ''] + table_metrics(semantic['overall'], baseline['overall'])
    for kind, title in [('HARD_NEGATIVE_CANDIDATE', 'Hard-negative FP'), ('EASY_NEGATIVE_CANDIDATE', 'Easy-negative FP')]:
        lines.append(f"| {title} | {semantic['groups'][kind]['FP']} | {baseline['groups'][kind]['FP']} |")
    lines += ['', '## 4. Best Exploratory F1 Comparison', '',
        'BOTH IN-SAMPLE EXPLORATORY; no production calibration or cherry-picking default versus best.']
    lines += table_metrics(dict(semantic['best_exploratory_f1_threshold'], roc_auc=semantic['overall']['roc_auc'], average_precision=semantic['overall']['average_precision']),
                           dict(baseline['best_exploratory_f1_threshold'], roc_auc=baseline['overall']['roc_auc'], average_precision=baseline['overall']['average_precision']))
    lines += ['', '## 5. Hard Negative Comparison', '', json.dumps(stats['hard_negative_head_to_head'], indent=2), '', '## 6. Easy Negative Comparison', '']
    for kind in ('HARD_NEGATIVE_CANDIDATE', 'EASY_NEGATIVE_CANDIDATE'):
        lines.append(f"{kind}: semantic FP={semantic['groups'][kind]['FP']}, baseline FP={baseline['groups'][kind]['FP']}; FPR={semantic['groups'][kind]['false_positive_rate']} / {baseline['groups'][kind]['false_positive_rate']}.")
    lines += ['', '## 7. False Positive Comparison', '', f"Semantic={semantic['overall']['FP']}; baseline={baseline['overall']['FP']}.", '',
        '## 8. False Negative Comparison', '', f"Semantic={semantic['overall']['FN']}; baseline={baseline['overall']['FN']}.", '',
        '## 9. Error Overlap', '', json.dumps(stats['error_overlap'], indent=2), '',
        '## 10. Ranking Quality', '', f"ROC-AUC={semantic['overall']['roc_auc']} / {baseline['overall']['roc_auc']}; AP={semantic['overall']['average_precision']} / {baseline['overall']['average_precision']}.", '',
        '## 11. Tradeoffs', '', 'Lower FP alone is not superiority: compare recall/FN, F1, specificity and ranking together. Different score scales make threshold 0.5 uncalibrated for both.', '',
        '## 12. Which method appears stronger?', '', 'See measured metrics and post-run review. Do not force a winner from accuracy alone; no held-out validation supports final deployment selection.', '',
        '## 13. Recommended Next Step', '', 'Reserve held-out, CV/JD-grouped calibration/testing data and evaluate chosen operating points. No hybrid or production switch is implemented.']
    (out / 'semantic_vs_baseline.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def run(args):
    started = time.perf_counter()
    input_hash = sha(args.input)
    if input_hash != EXPECTED_SHA:
        raise EvaluationDataError('Ground truth SHA differs from frozen 220-pair benchmark.')
    rows, validation = load_pairs(args.input, args.data_dir)
    semantic_dir = Path(args.semantic_dir)
    protected = {name: sha(semantic_dir / name) for name in SEMANTIC_FILES}
    semantic_metrics = json.loads((semantic_dir / 'metrics.json').read_text())
    if semantic_metrics['reproducibility']['input_sha256'] != input_hash:
        raise EvaluationDataError('Semantic benchmark uses different input hash.')
    if args.limit:
        rows = rows[:args.limit]
    cvs, jobs, files = sources(rows, args.data_dir)
    source_hashes = {name: sha(files[name]) for name in ('Resume.csv', 'job_postings.csv')}
    if source_hashes != semantic_metrics['reproducibility']['source_hashes']:
        raise EvaluationDataError('Semantic/baseline source hashes differ.')
    predictions = predict(rows, cvs, jobs, args.threshold)
    metrics, thresholds = summarize(predictions, args.threshold)
    try:
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    metrics.update(validation=validation, definition=definition(), runtime_seconds=time.perf_counter() - started,
        reproducibility=dict(input=str(Path(args.input).resolve()), input_sha256=input_hash, source_hashes=source_hashes,
            implementation_sha256=sha(Path(__file__).with_name('baseline_lexical.py')),
            frozen_definition_sha256=sha(Path(__file__).with_name('BASELINE_V1_FROZEN.md')),
            semantic_artifact_hashes=protected, git_commit=commit, command=sys.argv,
            timestamp=datetime.now(timezone.utc).isoformat(), partial=bool(args.limit), unique_cvs=len(cvs), unique_jobs=len(jobs)))
    semantic_rows = [r for _, r in iter_csv(semantic_dir / 'predictions.csv')]
    if any(int(r['predicted_label']) != int(float(r['semantic_score']) >= semantic_metrics['overall']['threshold']) for r in semantic_rows):
        raise EvaluationDataError('Stored semantic predictions do not match recorded threshold.')
    if args.limit:
        wanted = {r['pair_id'] for r in predictions}
        semantic_rows = [r for r in semantic_rows if r['pair_id'] in wanted]
    stats, overlap = compare(semantic_rows, predictions)
    # Recompute semantic metrics from its stored scores to validate comparison integrity.
    if not args.limit:
        computed = analyze(semantic_rows, semantic_metrics['overall']['threshold'])
        if computed != semantic_metrics['overall']:
            raise EvaluationDataError('Stored semantic metrics do not match predictions.')
    if input_hash != sha(args.input) or protected != {name: sha(semantic_dir / name) for name in SEMANTIC_FILES} or source_hashes != {name: sha(files[name]) for name in source_hashes}:
        raise EvaluationDataError('Input, sources or protected semantic artifacts changed during run.')
    write_results(Path(args.output_dir), predictions, metrics, thresholds)
    if not args.limit:
        write_comparison(Path(args.comparison_dir), semantic_metrics, metrics, stats, overlap)
    print(json.dumps(dict(validation=validation, overall=metrics['overall'], best=metrics['best_exploratory_f1_threshold'],
        comparison=stats, runtime_seconds=metrics['runtime_seconds']), indent=2))
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True); parser.add_argument('--data-dir', required=True)
    parser.add_argument('--output-dir', default='evaluation/results/baseline-v1')
    parser.add_argument('--semantic-dir', default='evaluation/results/semantic-v1')
    parser.add_argument('--comparison-dir', default='evaluation/results/comparison')
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args(argv)
    if not math.isfinite(args.threshold) or not 0 <= args.threshold <= 1 or (args.limit is not None and args.limit < 1):
        parser.error('Invalid threshold/limit.')
    if len({Path(p).resolve() for p in (args.output_dir, args.semantic_dir, args.comparison_dir)}) != 3:
        parser.error('Baseline, semantic and comparison directories must differ.')
    if any((Path(args.output_dir) / name).exists() for name in ('metrics.json', 'report.md', 'predictions.csv')) or (Path(args.comparison_dir) / 'semantic_vs_baseline.md').exists():
        parser.error('Results already exist; use fresh output/comparison directories.')
    try:
        run(args)
    except EvaluationDataError as exc:
        parser.exit(1, f'Benchmark stopped: {exc}\n')


if __name__ == '__main__':
    main()
