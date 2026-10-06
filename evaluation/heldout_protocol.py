"""Frozen, deterministic grouped splitting and calibration-only selection."""
import hashlib
import math
import random
from collections import Counter, defaultdict
from fractions import Fraction

from evaluation.benchmark_metrics import analyze, classification, ranking
from evaluation.common import EvaluationDataError, PAIR_TYPES, stable_rank

POLICY = {'version': 'grouped-retrospective-holdout-v1', 'seed': 42,
          'calibration_fraction': .6, 'calibration_range': [.55, .65],
          'grouping': 'connected components of typed bipartite CV/JD graph',
          'selection': 'max calibration F1, higher precision, lower FP, higher threshold',
          'threshold_candidates': 'observed calibration scores, adjacent midpoints, range endpoints, nextafter(max,+inf)',
          'comparison': 'score >= threshold', 'bootstrap_resamples': 1000,
          'limitations': ['Retrospective partition: all 220 labels previously analyzed.',
                         'Frozen baseline IDF used the full corpus: transductive covariate exposure.',
                         'Not a new blind external or fully inductive test.']}


def components(rows):
    adjacency = defaultdict(set)
    edge_rows = defaultdict(list)
    ids = set()
    for row in rows:
        if row['pair_id'] in ids:
            raise EvaluationDataError('Duplicate pair ID in graph.')
        ids.add(row['pair_id'])
        cv, job = ('cv', row['cv_id']), ('job', row['job_id'])
        adjacency[cv].add(job); adjacency[job].add(cv)
        edge_rows[cv].append(row)
    seen, groups = set(), []
    for node in sorted(adjacency):
        if node in seen:
            continue
        stack, members = [node], []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current); members.extend(edge_rows[current])
            stack.extend(sorted(adjacency[current] - seen, reverse=True))
        members.sort(key=lambda r: r['pair_id'])
        cid = 'component_' + hashlib.sha256('\n'.join(r['pair_id'] for r in members).encode()).hexdigest()[:16]
        groups.append({'component_id': cid, 'rows': members})
    return sorted(groups, key=lambda g: g['component_id'])


def statistics(rows):
    return {'pairs': len(rows), 'positive': sum(int(r['human_label']) for r in rows),
            'negative': sum(1 - int(r['human_label']) for r in rows),
            'candidate_groups': dict(Counter(r['candidate_type'] for r in rows)),
            'hard_human_negative': sum(r['candidate_type'] == 'HARD_NEGATIVE_CANDIDATE' and r['human_label'] == '0' for r in rows),
            'easy_human_negative': sum(r['candidate_type'] == 'EASY_NEGATIVE_CANDIDATE' and r['human_label'] == '0' for r in rows),
            'unique_cvs': len({r['cv_id'] for r in rows}), 'unique_jobs': len({r['job_id'] for r in rows})}


def features(rows):
    stats = statistics(rows)
    return (stats['pairs'], stats['positive'], *(stats['candidate_groups'].get(kind, 0) for kind in PAIR_TYPES),
            stats['hard_human_negative'], stats['easy_human_negative'])


def leakage(calibration, test, original):
    counts = {key: len({r[key] for r in calibration} & {r[key] for r in test}) for key in ('cv_id', 'job_id', 'pair_id')}
    combined = calibration + test
    if any(counts.values()) or len(combined) != len(original) or {r['pair_id'] for r in combined} != {r['pair_id'] for r in original}:
        raise EvaluationDataError('Split leaks identity, duplicates or loses rows.')
    by_id = {r['pair_id']: r for r in original}
    if any(any(r[key] != by_id[r['pair_id']][key] for key in ('cv_id', 'job_id', 'human_label', 'candidate_type')) for r in combined):
        raise EvaluationDataError('Split changed source references or labels.')
    return counts


def grouped_split(rows, seed=42):
    groups = components(rows)
    if len(groups) < 2:
        raise EvaluationDataError('Giant component: leakage-free split impossible.')
    total = features(rows)
    vectors = [features(g['rows']) for g in groups]
    weights = (25, 10, 1, 1, 1, 1, 1)
    def loss(vector):
        return sum(weight * (5 * actual - 3 * target) ** 2 for weight, actual, target in zip(weights, vector, total))
    def add(left, right, sign=1):
        return tuple(a + sign * b for a, b in zip(left, right))
    order = sorted(range(len(groups)), key=lambda i: (-vectors[i][0], stable_rank(seed, groups[i]['component_id'])))
    selected, vector = set(), (0,) * len(total)
    for i in order:
        if loss(add(vector, vectors[i])) < loss(vector):
            selected.add(i); vector = add(vector, vectors[i])
    # Strictly decreasing integer objective; only label/group counts, never scores.
    for _ in range(1000):
        candidates = []
        for i in order:
            candidate = add(vector, vectors[i], -1 if i in selected else 1)
            candidates.append((loss(candidate), stable_rank(seed, 'flip', groups[i]['component_id']), (i,), candidate))
        for i in order:
            if i not in selected:
                continue
            for j in order:
                if j in selected:
                    continue
                candidate = add(add(vector, vectors[i], -1), vectors[j])
                candidates.append((loss(candidate), stable_rank(seed, 'swap', groups[i]['component_id'], groups[j]['component_id']), (i, j), candidate))
        best = min(candidates)
        if best[0] >= loss(vector):
            break
        for i in best[2]:
            selected.symmetric_difference_update({i})
        vector = best[3]
    else:
        raise EvaluationDataError('Split search did not converge; no partition published.')
    calibration, test = [], []
    for i, group in enumerate(groups):
        split = 'calibration' if i in selected else 'test'
        destination = calibration if i in selected else test
        destination.extend(dict(r, split=split, component_id=group['component_id']) for r in group['rows'])
    calibration.sort(key=lambda r: r['pair_id']); test.sort(key=lambda r: r['pair_id'])
    if not .55 <= len(calibration) / len(rows) <= .65:
        raise EvaluationDataError('No reasonable grouped 55–65% calibration partition found; components are not broken.')
    if any({r['human_label'] for r in subset} != {'0', '1'} for subset in (calibration, test)):
        raise EvaluationDataError('Both labels are required in both partitions.')
    checks = leakage(calibration, test, rows)
    return calibration, test, {'component_count': len(groups), 'component_size_distribution': dict(Counter(len(g['rows']) for g in groups)),
        'largest_component': max(len(g['rows']) for g in groups),
        'top10': [{'component_id': g['component_id'], 'pairs': len(g['rows'])} for g in sorted(groups, key=lambda g: (-len(g['rows']), g['component_id']))[:10]],
        'calibration': statistics(calibration), 'test': statistics(test), 'leakage': checks,
        'calibration_fraction': len(calibration) / len(rows), 'objective': loss(vector)}


def threshold_key(result):
    tp, fp, fn = result['TP'], result['FP'], result['FN']
    return (Fraction(2 * tp, 2 * tp + fp + fn) if 2 * tp + fp + fn else Fraction(-1),
            Fraction(tp, tp + fp) if tp + fp else Fraction(-1), -fp, result['threshold'])


def select_threshold(calibration_rows, score_field, minimum, maximum):
    """Only calibration rows are accepted; no test/global distribution input."""
    if not calibration_rows or {r['human_label'] for r in calibration_rows} != {'0', '1'}:
        raise EvaluationDataError('Calibration must contain both labels.')
    scores = [float(r[score_field]) for r in calibration_rows]
    if any(not math.isfinite(score) or not minimum <= score <= maximum for score in scores):
        raise EvaluationDataError('Invalid calibration score.')
    unique = sorted(set(scores))
    candidates = {minimum, maximum, *unique, math.nextafter(max(unique), math.inf)}
    candidates.update(a + (b - a) / 2 for a, b in zip(unique, unique[1:]))
    labels = [int(r['human_label']) for r in calibration_rows]
    sweep = [classification(labels, scores, threshold) for threshold in sorted(candidates)]
    return max(sweep, key=threshold_key), sweep


def evaluate(rows, thresholds):
    """No optimizer here: consume persisted calibration-frozen thresholds."""
    return {name: {'overall': analyze(rows, frozen['threshold'], frozen['score_field']),
                   'groups': {kind: analyze([r for r in rows if r['candidate_type'] == kind], frozen['threshold'], frozen['score_field']) for kind in PAIR_TYPES}}
            for name, frozen in thresholds.items()}


def bootstrap(rows, thresholds, count=1000, seed=42):
    rng = random.Random(seed)
    results = {name: defaultdict(list) for name in thresholds}
    differences = []
    for _ in range(count):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        labels = [int(r['human_label']) for r in sample]
        f1 = {}
        for name, frozen in thresholds.items():
            scores = [float(r[frozen['score_field']]) for r in sample]
            metrics = classification(labels, scores, frozen['threshold']) | ranking(labels, scores)
            f1[name] = metrics['f1']
            for key in ('precision', 'recall', 'f1', 'roc_auc', 'average_precision'):
                if metrics[key] is not None:
                    results[name][key].append(metrics[key])
        if all(value is not None for value in f1.values()):
            differences.append(f1['baseline-v1'] - f1['semantic-v1'])
    def interval(values):
        ordered = sorted(values)
        def quantile(q):
            p = (len(ordered) - 1) * q; lo, hi = math.floor(p), math.ceil(p)
            return ordered[lo] + (ordered[hi] - ordered[lo]) * (p - lo)
        return {'low': quantile(.025), 'high': quantile(.975), 'valid_resamples': len(values)} if values else {'low': None, 'high': None, 'valid_resamples': 0}
    return {'seed': seed, 'resamples': count, 'method': 'paired row percentile bootstrap after grouping; thresholds fixed',
            'limitation': 'Rows sharing entities inside test are dependent; row intervals may understate uncertainty.',
            'intervals': {name: {key: interval(values) for key, values in metrics.items()} for name, metrics in results.items()},
            'paired_f1_delta_baseline_minus_semantic': interval(differences)}
