import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.common import EvaluationDataError
from evaluation.hybrid_protocol import (ALPHAS, apply_config, bootstrap_hybrid, calibrate, choose,
    ecdf_fit, ecdf_transform, eligible, error_overlap, fuse, selection_key, summarize)
from evaluation import run_hybrid_experiment as runner


def row(i):
    return {'pair_id': f'p{i}', 'cv_id': f'c{i}', 'job_id': f'j{i}', 'human_label': str(i % 2),
        'candidate_type': 'HARD_NEGATIVE_CANDIDATE', 'label_reason': 'Synthetic professional reason.',
        'semantic_score': .8 if i % 2 else .3, 'baseline_score': .7 if i % 2 else .2}


def candidate(tp=8, tn=8, fp=2, fn=2, threshold=.5, alpha=.5):
    return {'TP': tp, 'TN': tn, 'FP': fp, 'FN': fn, 'threshold': threshold, 'alpha': alpha}


def test_ecdf_ties_bounds_and_unseen_scores():
    state = ecdf_fit([.8, .2, .2, .5])
    assert state == [.2, .2, .5, .8]
    assert [ecdf_transform(state, value) for value in (.1, .2, .4, .8, 1.)] == [0, .5, .5, 1, 1]
    assert state == ecdf_fit(list(reversed([.8, .2, .2, .5])))
    with pytest.raises(EvaluationDataError):
        ecdf_fit([float('nan')])


@pytest.mark.parametrize('alpha', ALPHAS)
def test_exact_fusion(alpha):
    assert fuse(.8, .2, alpha) == alpha * .8 + (1 - alpha) * .2


def test_rank_fusion_does_not_break_mathematical_ties():
    state = {'semantic': list(range(12)), 'baseline': list(range(12))}
    data = [dict(row(0), semantic_score=0, baseline_score=3), dict(row(1), semantic_score=3, baseline_score=2)]
    output = apply_config(data, {'alpha': .25, 'ecdf_state': state})
    assert output[0]['hybrid_score'] == output[1]['hybrid_score']  #1+3*4 =4+3*3


@pytest.mark.parametrize('alpha', [.33, .6, .9])
def test_unsupported_alpha_rejected(alpha):
    with pytest.raises(EvaluationDataError):
        fuse(.8, .2, alpha)
    with pytest.raises(EvaluationDataError):
        choose([candidate(alpha=alpha)])


def test_recall_floor_and_rejected_candidate_cannot_win():
    assert eligible(candidate(tp=8, fn=2))
    assert eligible(candidate(tp=9, fn=1))
    assert not eligible(candidate(tp=7, fn=3))
    good = candidate(tp=8, fn=2, tn=6, fp=4)
    rejected = candidate(tp=7, fn=3, tn=10, fp=0)
    selected, fallback = choose([rejected, good])
    assert selected == good and not fallback


def test_primary_and_fallback_order():
    low_fp = candidate(tn=9, fp=1)
    high_specificity = candidate(tn=18, fp=2)
    assert selection_key(low_fp) > selection_key(high_specificity)  # same specificity -> lowerFP
    assert selection_key(candidate(tp=9, fn=1)) > selection_key(candidate(tp=8, fn=2))
    assert selection_key(candidate(threshold=.6)) > selection_key(candidate(threshold=.5))
    assert selection_key(candidate(alpha=.5)) > selection_key(candidate(alpha=.25))
    a = candidate(tp=7, fn=3, tn=5, fp=5)
    b = candidate(tp=6, fn=4, tn=10, fp=0)
    selected, fallback = choose([b, a])
    assert selected == a and fallback
    # Equal recall: specificity, then FP, F1, precision, threshold, closest alpha.
    assert selection_key(candidate(tp=7, fn=3, tn=9, fp=1), True) > selection_key(a, True)
    assert selection_key(candidate(tp=7, fn=3, threshold=.6), True) > selection_key(candidate(tp=7, fn=3), True)


def test_calibration_only_no_heldout_fresh_influence():
    calibration = [row(i) for i in range(20)]
    config, selection = calibrate(calibration)
    assert len(selection['alternatives']) == 3
    assert {r['alpha'] for r in selection['alternatives']} == set(ALPHAS)
    assert any(not r['eligible'] for a in selection['alternatives'] for r in a['sweep'])
    external = [dict(row(i), human_label='0', semantic_score=-.99, baseline_score=.99) for i in range(30, 40)]
    before = copy.deepcopy(config)
    apply_config(external, config)
    assert config == before == calibrate(calibration)[0]
    assert len(config['ecdf_state']['semantic']) == 20


def test_complementarity_and_hybrid_recovery_exact():
    thresholds = {'semantic-v1': {'score_field': 'semantic_score', 'threshold': .5},
        'baseline-v1': {'score_field': 'baseline_score', 'threshold': .5},
        'hybrid-v1': {'score_field': 'hybrid_score', 'threshold': .5}}
    rows = [dict(row(i), human_label='1', semantic_score=s, baseline_score=b, hybrid_score=h)
            for i, (s, b, h) in enumerate([(1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1)])]
    output, stats = error_overlap(rows, thresholds)
    assert [r['component_bucket'] for r in output] == ['BOTH_COMPONENTS_CORRECT', 'BOTH_COMPONENTS_WRONG', 'SEMANTIC_ONLY_CORRECT', 'BASELINE_ONLY_CORRECT']
    assert stats['recovery']['BOTH_COMPONENTS_CORRECT']['hybrid_wrong'] == 1
    assert stats['recovery']['BOTH_COMPONENTS_WRONG']['hybrid_correct'] == 1
    assert stats['recovery']['BASELINE_ONLY_CORRECT']['hybrid_correct'] == 1


def test_frozen_evaluation_cannot_refit(monkeypatch, tmp_path):
    temporary = tempfile.TemporaryDirectory(prefix='hybrid-freeze-test-', dir=tmp_path)
    try:
        out = Path(temporary.name)
        rows = [row(i) for i in range(20)]
        config, selection = calibrate(rows)
        config['component_thresholds'] = {'semantic-v1': {'threshold': .5, 'score_field': 'semantic_score'},
                                         'baseline-v1': {'threshold': .5, 'score_field': 'baseline_score'}}
        runner.exclusive_json(out / 'hybrid_config.json', config)
        before = (out / 'hybrid_config.json').read_bytes()
        frozen = json.loads(before)
        monkeypatch.setattr(runner, 'calibrate', lambda *a, **k: pytest.fail('Evaluation optimizer forbidden'))
        import evaluation.hybrid_protocol as protocol
        monkeypatch.setattr(protocol, 'ecdf_fit', lambda *a, **k: pytest.fail('Evaluation normalization refit forbidden'))
        predictions, metrics, thresholds = runner.evaluate_rows(rows, frozen)
        assert metrics['hybrid-v1']['overall']['count'] == 20
        assert before == (out / 'hybrid_config.json').read_bytes()
        assert bootstrap_hybrid(predictions, thresholds, 20) == bootstrap_hybrid(predictions, thresholds, 20)
    finally:
        temporary.cleanup()


def test_runner_imports_no_providers_db_or_network():
    code = "import sys,socket; socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network forbidden')); import evaluation.run_hybrid_experiment; assert not any(m.startswith(('app.', 'sqlalchemy','httpx')) for m in sys.modules)"
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
