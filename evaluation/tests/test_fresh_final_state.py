import copy
import json
import math

import pytest

from evaluation.baseline_lexical import LexicalBaseline
from evaluation.fresh_final_state import development_state, transform_only
from evaluation.heldout_protocol import evaluate, bootstrap


def test_development_state_reproduces_original_and_contains_no_raw_terms():
    docs = {'c': 'Python SQL Alice developer', 'j': 'Python SQL developer'}
    original, state = development_state(docs)
    rebuilt = transform_only(state, docs)
    assert rebuilt.score('c', 'j', 'Python developer') == original.score('c', 'j', 'Python developer')
    dumped = json.dumps(state)
    assert 'Alice' not in dumped and 'python' not in dumped and 'developer' not in dumped
    assert state['development_document_count'] == 2


def test_fresh_transform_never_fits_or_changes_idf(monkeypatch):
    original, state = development_state({'dc': 'alpha beta', 'dj': 'alpha gamma'})
    before = copy.deepcopy(state)
    monkeypatch.setattr(LexicalBaseline, '__init__', lambda *a, **k: pytest.fail('Fresh constructor fit forbidden'))
    new = transform_only(state, {'c': 'alpha omega omega', 'j': 'alpha theta'})
    assert new.score('c', 'j', 'omega') == pytest.approx(1.)  # same known TF-IDF vector + literal title coverage
    assert state == before
    assert set(new.vectors['c']) == {'alpha'} and set(new.counts['c']) == {'alpha', 'omega'}
    unknown = transform_only(state, {'c': 'omega', 'j': 'theta'})
    assert unknown.score('c', 'j', 'omega') == pytest.approx(.3)


def test_fixed_threshold_evaluation_no_optimizer(monkeypatch):
    import evaluation.heldout_protocol as protocol
    monkeypatch.setattr(protocol, 'select_threshold', lambda *a, **k: pytest.fail('Fresh tuning forbidden'))
    rows = [{'pair_id': str(i), 'human_label': str(i % 2), 'candidate_type': 'HARD_NEGATIVE_CANDIDATE',
             'semantic_score': .8 if i % 2 else .2, 'baseline_score': .7 if i % 2 else .1} for i in range(10)]
    thresholds = {'semantic-v1': {'threshold': .6, 'score_field': 'semantic_score'},
                  'baseline-v1': {'threshold': .25, 'score_field': 'baseline_score'}}
    assert evaluate(rows, thresholds)['semantic-v1']['overall']['TP'] == 5
    assert bootstrap(rows, thresholds, 20)['paired_f1_delta_baseline_minus_semantic']['low'] == 0


def test_external_adapter_does_not_mutate_core_file():
    import hashlib
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'baseline_lexical.py'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    _, state = development_state({'c': 'alpha beta', 'j': 'alpha gamma'})
    transformed = transform_only(state, {'c': 'alpha omega', 'j': 'alpha theta'})
    transformed.score('c', 'j', 'alpha')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
