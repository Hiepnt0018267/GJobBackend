"""Frozen ECDF fusion family and calibration-only recruiter operating policy."""
import bisect
import math
import random
from collections import Counter, defaultdict
from fractions import Fraction

from evaluation.benchmark_metrics import analyze, classification, distribution, ranking
from evaluation.common import EvaluationDataError
from evaluation.heldout_protocol import evaluate

ALPHAS = (.25, .50, .75)
RECALL_FLOOR = Fraction(4, 5)
POLICY = {'version': 'hybrid-v1', 'alphas': list(ALPHAS), 'recall_floor': .8,
          'ecdf': 'count(calibration scores <= x) / calibration count; right-inclusive ties',
          'formula': 'alpha * semantic_normalized + (1-alpha) * baseline_normalized',
          'selection': ['specificity', 'lower_FP', 'F1', 'precision', 'recall', 'higher_threshold', 'alpha_closest_to_0.50'],
          'fallback': ['recall', 'specificity', 'lower_FP', 'F1', 'precision', 'higher_threshold', 'alpha_closest_to_0.50'],
          'complete_tie': 'first in fixed alpha order 0.25,0.50,0.75',
          'fusion_arithmetic': 'combine integer ECDF ranks over common 4N before final float division',
          'thresholds': 'calibration unique scores, adjacent midpoints,0,1,nextafter(max,+inf)',
          'prediction_rule': 'score >= threshold'}


def ecdf_fit(scores):
    if not scores or any(not math.isfinite(float(s)) for s in scores):
        raise EvaluationDataError('ECDF requires non-empty finite calibration scores.')
    return sorted(float(s) for s in scores)


def ecdf_transform(state, score):
    if not state or not math.isfinite(float(score)):
        raise EvaluationDataError('Invalid ECDF state/score.')
    return bisect.bisect_right(state, float(score)) / len(state)


def fuse(semantic_norm, baseline_norm, alpha):
    if alpha not in ALPHAS:
        raise EvaluationDataError('Unsupported hybrid alpha.')
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in (semantic_norm, baseline_norm)):
        raise EvaluationDataError('Normalized scores must be within [0,1].')
    return alpha * semantic_norm + (1 - alpha) * baseline_norm


def fractions(result):
    tp, tn, fp, fn = (result[k] for k in ('TP', 'TN', 'FP', 'FN'))
    def ratio(a, b):
        return Fraction(a, b) if b else Fraction(-1)
    return {'recall': ratio(tp, tp + fn), 'specificity': ratio(tn, tn + fp),
            'f1': ratio(2 * tp, 2 * tp + fp + fn), 'precision': ratio(tp, tp + fp)}


def eligible(result):
    return fractions(result)['recall'] >= RECALL_FLOOR


def selection_key(result, fallback=False):
    values = fractions(result)
    ending = (values['f1'], values['precision'], result['threshold'], -abs(result['alpha'] - .5))
    if fallback:
        return (values['recall'], values['specificity'], -result['FP'], *ending)
    return (values['specificity'], -result['FP'], values['f1'], values['precision'], values['recall'],
            result['threshold'], -abs(result['alpha'] - .5))


def choose(candidates):
    if not candidates:
        raise EvaluationDataError('No candidate configurations.')
    if any(r['alpha'] not in ALPHAS or not math.isfinite(r['threshold']) for r in candidates):
        raise EvaluationDataError('Unsupported alpha/threshold candidate.')
    accepted = [r for r in candidates if eligible(r)]
    fallback = not accepted
    return max(accepted or candidates, key=lambda r: selection_key(r, fallback)), fallback


def apply_config(rows, config):
    result = []
    state = config['ecdf_state']
    if len(state['semantic']) != len(state['baseline']) or not state['semantic'] or config['alpha'] not in ALPHAS:
        raise EvaluationDataError('Invalid equal-size calibration ECDF states/alpha.')
    alpha_numerator = int(config['alpha'] * 4)
    for row in rows:
        s = ecdf_transform(state['semantic'], row['semantic_score'])
        b = ecdf_transform(state['baseline'], row['baseline_score'])
        # Algebraically identical fusion, without ulp-splitting equal percentile sums.
        sr = bisect.bisect_right(state['semantic'], float(row['semantic_score']))
        br = bisect.bisect_right(state['baseline'], float(row['baseline_score']))
        hybrid = (alpha_numerator * sr + (4 - alpha_numerator) * br) / (4 * len(state['semantic']))
        result.append(dict(row, semantic_normalized=s, baseline_normalized=b, hybrid_score=hybrid))
    return result


def calibrate(calibration):
    if not calibration or {str(r['human_label']) for r in calibration} != {'0', '1'}:
        raise EvaluationDataError('Calibration requires both labels.')
    state = {'semantic': ecdf_fit([r['semantic_score'] for r in calibration]),
             'baseline': ecdf_fit([r['baseline_score'] for r in calibration])}
    candidates, alpha_reports = [], []
    for alpha in ALPHAS:
        rows = apply_config(calibration, {'alpha': alpha, 'ecdf_state': state})
        values = sorted({r['hybrid_score'] for r in rows})
        thresholds = {0., 1., *values, math.nextafter(values[-1], math.inf)}
        thresholds.update(a + (b - a) / 2 for a, b in zip(values, values[1:]))
        labels = [int(r['human_label']) for r in rows]
        scores = [r['hybrid_score'] for r in rows]
        sweep = []
        for threshold in sorted(thresholds):
            metrics = classification(labels, scores, threshold)
            metrics.update(alpha=alpha, eligible=eligible(metrics), hard_negative_FP=sum(
                r['candidate_type'] == 'HARD_NEGATIVE_CANDIDATE' and str(r['human_label']) == '0' and r['hybrid_score'] >= threshold for r in rows))
            sweep.append(metrics)
        chosen, fallback = choose(sweep)
        alpha_reports.append({'alpha': alpha, 'threshold_count': len(sweep),
                              'recall_floor_feasible': not fallback, 'best': chosen, 'sweep': sweep})
        candidates.extend(sweep)
    selected, fallback = choose(candidates)
    return {'algorithm': 'hybrid-v1', 'alpha': selected['alpha'], 'baseline_weight': 1 - selected['alpha'],
            'threshold': selected['threshold'], 'recall_floor': .8, 'normalization': 'ecdf',
            'normalization_fit_split': 'task14b4_calibration_only', 'ecdf_state': state,
            'selection_primary': 'specificity', 'selection_constraint': 'recall >= 0.80',
            'fallback_triggered': fallback, 'policy': POLICY, 'frozen': True}, {'alternatives': alpha_reports, 'selected': selected}


def summarize(rows, config, component_thresholds):
    thresholds = dict(component_thresholds, **{'hybrid-v1': {'score_field': 'hybrid_score', 'threshold': config['threshold']}})
    metrics = evaluate(rows, thresholds)
    metrics['normalized_distributions'] = {field: {
        'positive': distribution([r[field] for r in rows if str(r['human_label']) == '1']),
        'negative': distribution([r[field] for r in rows if str(r['human_label']) == '0'])}
        for field in ('semantic_normalized', 'baseline_normalized', 'hybrid_score')}
    h = metrics['hybrid-v1']['overall']
    metrics['tradeoffs'] = {name: {key + '_delta': h[key] - metrics[name]['overall'][key]
                                 for key in ('FP', 'FN', 'recall', 'specificity')}
                            for name in ('semantic-v1', 'baseline-v1')}
    metrics['hybrid_recall_floor_on_this_split'] = eligible(h)
    return metrics, thresholds


def error_overlap(rows, thresholds):
    output, recovery = [], defaultdict(Counter)
    for row in rows:
        y = int(row['human_label'])
        predictions = {name: int(row[value['score_field']] >= value['threshold']) for name, value in thresholds.items()}
        s, b, h = (predictions[k] == y for k in ('semantic-v1', 'baseline-v1', 'hybrid-v1'))
        bucket = {(True, True): 'BOTH_COMPONENTS_CORRECT', (False, False): 'BOTH_COMPONENTS_WRONG',
                  (True, False): 'SEMANTIC_ONLY_CORRECT', (False, True): 'BASELINE_ONLY_CORRECT'}[s, b]
        recovery[bucket]['count'] += 1
        recovery[bucket]['hybrid_correct'] += int(h)
        recovery[bucket]['hybrid_wrong'] += int(not h)
        output.append(dict(row, semantic_prediction=predictions['semantic-v1'], baseline_prediction=predictions['baseline-v1'],
            hybrid_prediction=predictions['hybrid-v1'], hybrid_correct=h, component_bucket=bucket))
    paired = {name: {'hybrid_correct_component_wrong': sum(int(r['hybrid_correct']) and int(r[prefix + '_prediction']) != int(r['human_label']) for r in output),
                    'component_correct_hybrid_wrong': sum(not r['hybrid_correct'] and int(r[prefix + '_prediction']) == int(r['human_label']) for r in output)}
              for name, prefix in [('semantic-v1', 'semantic'), ('baseline-v1', 'baseline')]}
    return output, {'recovery': {k: dict(v) for k, v in recovery.items()}, 'paired_errors': paired}


def bootstrap_hybrid(rows, thresholds, count=1000, seed=42):
    rng = random.Random(seed)
    stored, differences = {name: defaultdict(list) for name in thresholds}, defaultdict(list)
    for _ in range(count):
        sample = [rows[rng.randrange(len(rows))] for r in rows]
        labels = [int(r['human_label']) for r in sample]
        values = {}
        for name, frozen in thresholds.items():
            scores = [r[frozen['score_field']] for r in sample]
            result = classification(labels, scores, frozen['threshold']) | ranking(labels, scores)
            values[name] = result
            for key in ('f1', 'precision', 'recall', 'specificity', 'roc_auc', 'average_precision'):
                if result[key] is not None:
                    stored[name][key].append(result[key])
        for name in ('semantic-v1', 'baseline-v1'):
            for key in ('f1', 'specificity', 'recall'):
                h, c = values['hybrid-v1'][key], values[name][key]
                if h is not None and c is not None:
                    differences[f'hybrid_minus_{name}_{key}'].append(h - c)
    def interval(values):
        values = sorted(values)
        def q(fraction):
            position = (len(values) - 1) * fraction
            low, high = math.floor(position), math.ceil(position)
            return values[low] + (values[high] - values[low]) * (position - low)
        return {'low': q(.025), 'high': q(.975), 'valid_resamples': len(values)} if values else {'low': None, 'high': None, 'valid_resamples': 0}
    return {'seed': seed, 'resamples': count, 'thresholds_and_ecdf_fixed': True,
            'intervals': {name: {key: interval(v) for key, v in metrics.items()} for name, metrics in stored.items()},
            'paired_differences': {key: interval(v) for key, v in differences.items()},
            'limitation': 'Conditional paired row percentile bootstrap; not selection/split uncertainty or new independent validation.'}
