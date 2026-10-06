"""Dependency-free classification/ranking metrics for offline evaluation."""
import math
import statistics


def divide(numerator, denominator):
    return numerator / denominator if denominator else None


def classification(labels, scores, threshold):
    counts = dict(TP=0, TN=0, FP=0, FN=0)
    for label, score in zip(labels, scores, strict=True):
        predicted = int(score >= threshold)
        counts[{(1, 1): 'TP', (0, 0): 'TN', (0, 1): 'FP', (1, 0): 'FN'}[label, predicted]] += 1
    tp, tn, fp, fn = (counts[k] for k in ('TP', 'TN', 'FP', 'FN'))
    recall, specificity = divide(tp, tp + fn), divide(tn, tn + fp)
    return dict(counts, threshold=threshold, precision=divide(tp, tp + fp), recall=recall,
                f1=divide(2 * tp, 2 * tp + fp + fn), accuracy=divide(tp + tn, len(labels)),
                specificity=specificity, false_positive_rate=divide(fp, fp + tn),
                balanced_accuracy=(recall + specificity) / 2 if recall is not None and specificity is not None else None,
                mcc=divide(tp * tn - fp * fn, math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))))


def ranking(labels, scores):
    # Group ties: ROC gives half credit; AP uses precision after each tied score block.
    positives, negatives = sum(labels), len(labels) - sum(labels)
    if not positives:
        return {'roc_auc': None, 'average_precision': None}
    blocks = {}
    for label, score in zip(labels, scores, strict=True):
        blocks.setdefault(score, []).append(label)
    below, concordant = 0, 0
    for score in sorted(blocks):
        block = blocks[score]; p = sum(block); n = len(block) - p
        concordant += p * (below + n / 2)
        below += n
    seen, true_seen, ap = 0, 0, 0.0
    for score in sorted(blocks, reverse=True):
        block = blocks[score]; p = sum(block)
        seen += len(block); true_seen += p
        ap += (p / positives) * (true_seen / seen)
    return {'roc_auc': divide(concordant, positives * negatives), 'average_precision': ap}


def distribution(values):
    if not values:
        return {'count': 0, 'mean': None, 'median': None, 'percentiles': {}}
    ordered = sorted(values)
    def percentile(q):
        position = (len(ordered) - 1) * q
        low, high = math.floor(position), math.ceil(position)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {'count': len(values), 'mean': statistics.mean(values), 'median': statistics.median(values),
            'percentiles': {str(p): percentile(p / 100) for p in (0, 5, 25, 50, 75, 95, 100)}}


def analyze(rows, threshold, score_field='semantic_score'):
    labels = [int(r['human_label']) for r in rows]
    scores = [float(r[score_field]) for r in rows]
    return {'count': len(rows), 'human_positive': sum(labels), 'human_negative': len(rows) - sum(labels),
            'positive_ratio': divide(sum(labels), len(rows)), 'negative_ratio': divide(len(rows) - sum(labels), len(rows)),
            **classification(labels, scores, threshold), **ranking(labels, scores),
            'score_distribution': distribution(scores),
            'positive_scores': distribution([s for y, s in zip(labels, scores) if y == 1]),
            'negative_scores': distribution([s for y, s in zip(labels, scores) if y == 0])}


def errors(rows, label, score_field='semantic_score'):
    return sorted((r for r in rows if int(r['human_label']) == label and int(r['predicted_label']) != label),
                  key=lambda r: ((-1 if label == 0 else 1) * float(r[score_field]), r['pair_id']))


def threshold_analysis(rows, threshold, score_field, minimum=0., maximum=1.):
    """Same policy: 0.05 grid plus observed scores and all-negative boundary."""
    labels = [int(r['human_label']) for r in rows]
    scores = [float(r[score_field]) for r in rows]
    count = round((maximum - minimum) / .05)
    grid = {round(minimum + i * .05, 6) for i in range(count + 1)} | {threshold} | set(scores)
    grid.add(math.nextafter(max(scores), math.inf))
    results = [classification(labels, scores, value) for value in sorted(grid)]
    best = max(results, key=lambda r: (r['f1'] if r['f1'] is not None else -1, r['threshold']))
    return results, best
