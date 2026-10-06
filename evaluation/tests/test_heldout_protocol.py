import copy
import json
import math
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.common import EvaluationDataError
from evaluation.heldout_protocol import bootstrap, components, evaluate, grouped_split, select_threshold, threshold_key
from evaluation import run_heldout_evaluation as runner


def row(i, cv=None, job=None, label=None):
    return {'pair_id': f'p{i}', 'cv_id': cv or f'c{i}', 'job_id': job or f'j{i}',
            'human_label': str(i % 2 if label is None else label),
            'candidate_type': ('POSITIVE_CANDIDATE', 'HARD_NEGATIVE_CANDIDATE', 'EASY_NEGATIVE_CANDIDATE')[i % 3],
            'label_reason': 'Synthetic professional evidence.',
            'semantic_score': .8 if i % 2 else .2, 'baseline_score': .7 if i % 2 else .1}


def test_shared_cv_jd_chain_typed_nodes_and_determinism():
    rows = [row(0, 'a', 'x'), row(1, 'b', 'x'), row(2, 'b', 'y')] + [row(i) for i in range(3, 30)]
    groups = components(rows)
    chain = next(g for g in groups if any(r['pair_id'] == 'p0' for r in g['rows']))
    assert {r['pair_id'] for r in chain['rows']} == {'p0', 'p1', 'p2'}
    cal, test, audit = grouped_split(rows)
    second = grouped_split(list(reversed(rows)))
    assert [r['pair_id'] for r in cal] == [r['pair_id'] for r in second[0]]
    assert {r['split'] for r in cal + test if r['pair_id'] in {'p0', 'p1', 'p2'}} in ({'calibration'}, {'test'})
    assert audit['leakage'] == {'cv_id': 0, 'job_id': 0, 'pair_id': 0}
    assert len(cal) + len(test) == len(rows)
    assert len(components([row(0, 'same', 'x'), row(1, 'y', 'same')])) == 2
    changed_scores = [dict(r, semantic_score=-1, baseline_score=1) for r in rows]
    assert [r['pair_id'] for r in grouped_split(changed_scores)[0]] == [r['pair_id'] for r in cal]


def test_giant_and_unreasonable_group_structure_stop():
    with pytest.raises(EvaluationDataError, match='Giant component'):
        grouped_split([row(i, cv='shared') for i in range(20)])
    rows = [row(i, cv='giant') for i in range(19)] + [row(19)]
    with pytest.raises(EvaluationDataError, match='reasonable'):
        grouped_split(rows)


def test_balance_never_breaks_components():
    # Six components of four cannot yield 55–65% of 24; stop rather than cut.
    impossible = [row(i, cv=f'group{i // 4}', label=int(i >= 12)) for i in range(24)]
    with pytest.raises(EvaluationDataError, match='reasonable'):
        grouped_split(impossible)
    rows = [row(i, cv=f'group{i // 3}', label=int(i >= 12)) for i in range(24)]
    cal, test, audit = grouped_split(rows)
    assert .55 <= audit['calibration_fraction'] <= .65
    assert {r['cv_id'] for r in cal}.isdisjoint(r['cv_id'] for r in test)
    assert {r['human_label'] for r in cal} == {r['human_label'] for r in test} == {'0', '1'}


def test_calibration_boundaries_and_test_label_isolation():
    cal = [dict(row(i), semantic_score=score, human_label=str(label)) for i, (score, label) in enumerate([(.1, 0), (.4, 1), (.5, 0), (.8, 1)])]
    selected, sweep = select_threshold(cal, 'semantic_score', -1, 1)
    assert selected['f1'] == max(r['f1'] or 0 for r in sweep)
    assert any(r['threshold'] == .25 for r in sweep)  # adjacent midpoint
    test = [row(20), row(21)]
    changed = [dict(r, human_label='1' if r['human_label'] == '0' else '0', semantic_score=-.99) for r in test]
    assert test != changed
    assert select_threshold(cal, 'semantic_score', -1, 1)[0] == selected
    assert selected['threshold'] <= max(r['semantic_score'] for r in cal)


def test_threshold_tie_order_exact():
    # Equal F1: 1/2. Higher precision wins before FP or threshold.
    a = {'TP': 1, 'FP': 0, 'FN': 2, 'threshold': .2}
    b = {'TP': 2, 'FP': 3, 'FN': 1, 'threshold': .9}
    assert threshold_key(a) > threshold_key(b)
    # Same F1/precision: lower FP (proportional count triples) wins.
    a = {'TP': 1, 'FP': 1, 'FN': 1, 'threshold': .2}
    b = {'TP': 2, 'FP': 2, 'FN': 2, 'threshold': .9}
    assert threshold_key(a) > threshold_key(b)
    assert threshold_key(dict(a, threshold=.5)) > threshold_key(a)


@pytest.fixture
def lifecycle(tmp_path):
    temporary = tempfile.TemporaryDirectory(prefix='heldout-fixtures-', dir=tmp_path)
    root = Path(temporary.name)
    args = SimpleNamespace(derived_dir=str(root / 'derived'), reports_dir=str(root / 'reports'), output_dir=str(root / 'output'), seed=42)
    source = root / 'source.csv'; source.write_text('synthetic fixture only', encoding='utf-8')
    rows = [row(i) for i in range(30)]
    runner.split_phase(args, rows, {str(source): runner.sha(source)}, {'rows': 30})
    yield args, rows, root
    temporary.cleanup()


def test_freeze_and_single_evaluation_no_test_optimizer(lifecycle, monkeypatch):
    args, rows, root = lifecycle
    runner.calibrate_phase(args, rows)
    path = Path(args.output_dir) / 'calibrated_thresholds.json'
    frozen_bytes = path.read_bytes()
    with pytest.raises(EvaluationDataError, match='already frozen'):
        runner.calibrate_phase(args, rows)
    monkeypatch.setattr(runner, 'select_threshold', lambda *a, **k: pytest.fail('Test phase cannot optimize'))
    runner.test_phase(args, rows)
    assert path.read_bytes() == frozen_bytes
    with pytest.raises(FileExistsError):
        runner.test_phase(args, rows)
    metrics = json.loads((Path(args.output_dir) / 'test_metrics.json').read_text())
    assert metrics['threshold_artifact_sha256'] == runner.sha(path)
    assert (Path(args.output_dir) / 'test_predictions.csv').is_file()
    assert (Path(args.output_dir) / 'baseline_false_negatives.csv').is_file()
    assert all(v['overall']['count'] == 12 for v in metrics['algorithms'].values())


def test_tampered_partition_and_threshold_rejected(lifecycle):
    args, rows, root = lifecycle
    runner.calibrate_phase(args, rows)
    path = Path(args.output_dir) / 'calibrated_thresholds.json'
    original = path.read_bytes(); data = json.loads(original)
    data['algorithms']['semantic-v1']['threshold'] = .01
    path.write_text(json.dumps(data))
    with pytest.raises(EvaluationDataError, match='artifact changed'):
        runner.test_phase(args, rows)
    path.write_bytes(original)
    partition = Path(args.derived_dir) / 'test_pairs.csv'
    partition.write_text(partition.read_text() + '\n')
    with pytest.raises(EvaluationDataError, match='CSV changed'):
        runner.test_phase(args, rows)


def test_bootstrap_deterministic_and_fixed_threshold(monkeypatch):
    import evaluation.heldout_protocol as module
    monkeypatch.setattr(module, 'select_threshold', lambda *a, **k: pytest.fail('Bootstrap cannot tune'))
    rows = [row(i) for i in range(12)]
    thresholds = {'semantic-v1': {'threshold': .5, 'score_field': 'semantic_score'},
                  'baseline-v1': {'threshold': .5, 'score_field': 'baseline_score'}}
    assert evaluate(rows, thresholds)['semantic-v1']['overall']['f1'] == 1
    first = bootstrap(rows, thresholds, 20)
    assert first == bootstrap(rows, thresholds, 20)
    assert first['paired_f1_delta_baseline_minus_semantic']['low'] == 0


def test_no_provider_database_imports():
    import subprocess
    import sys
    code = "import sys,socket; socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network forbidden')); import evaluation.run_heldout_evaluation; assert not any(m.startswith(('app.', 'httpx', 'sqlalchemy')) for m in sys.modules)"
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
