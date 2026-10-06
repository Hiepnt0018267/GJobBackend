import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from evaluation.common import EvaluationDataError, make_pair_id
from evaluation.fresh_labeling import FreshLabelingStore
from evaluation.fresh_test_protocol import validate_fresh_labels, validate_fresh_rows
from evaluation.generate_fresh_test_pairs import FIELDS, mine_fresh
from evaluation.labeling_ai import LabelingAI
from evaluation.labeling_app import create_app, output_for_input, progress_for_input
from evaluation.labeling_store import atomic_csv
from evaluation.tests.test_hard_generation import source


@pytest.fixture
def fresh(source, tmp_path, request):
    data, old_rows, _ = source
    temporary = tempfile.TemporaryDirectory(prefix='fresh-fixture-', dir=tmp_path)
    request.addfinalizer(temporary.cleanup)
    def cleanup_sources():
        assert data.resolve().parent == tmp_path.resolve() and data.name == 'data'
        shutil.rmtree(data)
    request.addfinalizer(cleanup_sources)
    root = Path(temporary.name)
    old = root / 'evaluation_pairs_labeled.csv'
    atomic_csv(old, [dict(old_rows[0], label='1', label_reason='Historical decision unchanged.')], list(old_rows[0]))
    rows, report = mine_fresh(data, old, quotas=(1, 2, 1), sample_size=6)
    seed = root / 'fresh_test_pairs_seed.csv'
    atomic_csv(seed, rows, FIELDS)
    return data, old, seed, rows, report


def make_store(fresh):
    data, old, seed, _, _ = fresh
    return FreshLabelingStore(seed, data, progress_for_input(seed), output_for_input(seed),
                              old_benchmark=old, min_rows=4, max_rows=4)


def test_generation_exclusion_uniqueness_determinism_label_independence(fresh):
    data, old, seed, rows, report = fresh
    assert len(rows) == len({r['cv_id'] for r in rows}) == len({r['job_id'] for r in rows}) == 4
    assert all(r['cv_id'] != 'c0' and r['job_id'] != 'j0' and r['pair_id'] != make_pair_id('c0', 'j0') for r in rows)
    assert all(r['label'] == r['label_reason'] == r['sampling_score'] == r['cv_text_preview'] == r['job_text_preview'] == '' for r in rows)
    second, _ = mine_fresh(data, old, quotas=(1, 2, 1), sample_size=6)
    assert rows == second
    with old.open(encoding='utf-8', newline='') as handle:
        old_rows = list(csv.DictReader(handle))
    old_rows[0].update(label='0', label_reason='Different historical decision must not alter generation.')
    atomic_csv(old, old_rows, list(old_rows[0]))
    third, _ = mine_fresh(data, old, quotas=(1, 2, 1), sample_size=6)
    assert rows == third
    assert report['model_scores_computed'] is False


@pytest.mark.parametrize('problem', ['old_cv', 'old_jd', 'old_pair', 'duplicate', 'source', 'missing_cv', 'missing_jd', 'label', 'reason', 'bad_label', 'bad_id'])
def test_fresh_validator_rejects_bad_data(fresh, problem):
    data, old, seed, rows, _ = fresh
    labeled = [dict(r, label='1', label_reason='Explicit human evidence.') for r in rows]
    if problem == 'old_cv':
        labeled[0]['cv_id'] = 'c0'; labeled[0]['pair_id'] = make_pair_id('c0', labeled[0]['job_id'])
    elif problem == 'old_jd':
        labeled[0]['job_id'] = 'j0'; labeled[0]['pair_id'] = make_pair_id(labeled[0]['cv_id'], 'j0')
    elif problem == 'old_pair':
        labeled[0].update(cv_id='c0', job_id='j0', pair_id=make_pair_id('c0', 'j0'))
    elif problem == 'duplicate':
        labeled[1] = dict(labeled[0])
    elif problem == 'source':
        labeled[0]['cv_source_row'] = ''
    elif problem == 'missing_cv':
        labeled[0]['cv_id'] = 'missing'; labeled[0]['pair_id'] = make_pair_id('missing', labeled[0]['job_id'])
    elif problem == 'missing_jd':
        labeled[0]['job_id'] = 'missing'; labeled[0]['pair_id'] = make_pair_id(labeled[0]['cv_id'], 'missing')
    elif problem == 'label':
        labeled[0]['label'] = ''
    elif problem == 'bad_label':
        labeled[0]['label'] = '2'
    elif problem == 'reason':
        labeled[0]['label_reason'] = ' '
    elif problem == 'bad_id':
        labeled[0]['pair_id'] = 'invalid'
    with pytest.raises(EvaluationDataError):
        validate_fresh_rows(labeled, data, old, True, 4, 4)


def test_blind_api_qwen_and_human_confirmation(fresh):
    store = make_store(fresh)
    calls = []
    def handler(request):
        body = json.loads(request.content)
        evidence = json.loads(body['messages'][1]['content'])
        assert set(evidence) == {'cv_text', 'jd_title', 'jd_description'}
        assert 'Vietnamese' in body['messages'][0]['content']
        calls.append(evidence)
        return httpx.Response(200, json={'message': {'content': json.dumps({'suggested_label': 1, 'reason': 'CV thể hiện kinh nghiệm phù hợp với nhiệm vụ trong JD.'})}})
    ai = LabelingAI('http://localhost:11434', 'qwen3:8b', 'Human professional-fit rubric', httpx.MockTransport(handler))
    client = TestClient(create_app(store, ai))
    token = client.get('/').text.split("const token='")[1].split("'")[0]
    headers = {'x-review-token': token}
    pid = store.rows[0]['pair_id']
    store.rows[0].update(semantic_score='SECRET-SCORE', baseline_score='SECRET-SCORE', sampling_score='SECRET-SCORE')
    pair = client.get('/review/pairs/' + pid).json()
    assert pair['pair_type'] == '' and pair['cv']['category'] == ''
    assert 'SECRET-SCORE' not in json.dumps(pair)
    assert not {'semantic_score', 'baseline_score', 'threshold', 'candidate_type'} & set(pair)
    assert client.get('/review/state').json()['reviewed'] == 0
    assert client.post(f'/review/pairs/{pid}/suggestion', headers=headers, json={}).status_code == 200
    assert store.state(pid)['human_label'] == store.state(pid)['human_reason'] == ''
    assert client.post(f'/review/pairs/{pid}/decision', headers=headers, json={'label': '0', 'reason': 'Human-reviewed mismatch.'}).status_code == 200
    before = store.state(pid)
    assert client.post(f'/review/pairs/{pid}/suggestion', headers=headers, json={}).status_code == 200
    assert len(calls) == 2
    assert all(store.state(pid)[key] == before[key] for key in ('human_label', 'human_reason', 'review_status', 'reviewed_at'))
    assert client.post('/review/export', headers=headers, json={}).status_code == 400


def test_fresh_export_and_hash_scoped_resume_no_old_changes(fresh):
    data, old, seed, rows, _ = fresh
    original = old.read_bytes()
    store = make_store(fresh)
    with pytest.raises(EvaluationDataError):
        store.export()
    for row in store.rows:
        store.review(row['pair_id'], '1', 'Human-confirmed professional evidence.')
    assert store.export()['rows'] == 4
    assert old.read_bytes() == original
    assert make_store(fresh).summary()['reviewed'] == 4
    assert validate_fresh_labels(store.output_path, seed.parent / 'validated.csv', data_dir=data, old_benchmark=old, min_rows=4, max_rows=4)['rows'] == 4
    seed.write_bytes(seed.read_bytes() + b'\n')
    with pytest.raises(EvaluationDataError, match='hash mismatch'):
        make_store(fresh)
    assert old.read_bytes() == original


def test_prevents_historical_output_and_progress(fresh):
    data, old, seed, _, _ = fresh
    assert output_for_input(seed).name == 'fresh_test_pairs_labeled.csv'
    assert progress_for_input(seed).name == 'evaluation_labeling_progress_fresh_test_pairs_seed.csv'
    with pytest.raises(EvaluationDataError, match='historical'):
        FreshLabelingStore(seed, data, progress_for_input(seed), old, old_benchmark=old, min_rows=4, max_rows=4)
    with pytest.raises(EvaluationDataError, match='historical'):
        FreshLabelingStore(seed, data, seed.with_name('evaluation_labeling_progress.csv'), output_for_input(seed), old_benchmark=old, min_rows=4, max_rows=4)


def test_generator_imports_no_algorithm_provider_or_db():
    code = "import sys,socket; socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network forbidden')); import evaluation.generate_fresh_test_pairs; assert not any(m.startswith(('app.', 'sqlalchemy','httpx','evaluation.baseline_lexical','evaluation.run_semantic_benchmark','evaluation.run_baseline_benchmark')) for m in sys.modules)"
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_historical_pilot_excluded_conservatively(fresh):
    data, old, seed, rows, _ = fresh
    pilot = old.with_name('evaluation_pairs_pilot_reviewed.csv')
    atomic_csv(pilot, [{'pair_id': make_pair_id('c1', 'j4'), 'cv_id': 'c1', 'job_id': 'j4'}], ['pair_id', 'cv_id', 'job_id'])
    regenerated, report = mine_fresh(data, old, quotas=(1, 2, 1), sample_size=6)
    assert all(r['cv_id'] != 'c1' and r['job_id'] != 'j4' for r in regenerated)
    assert report['pool_audit']['additional_historical_cv_ids'] == 1
    assert report['pool_audit']['additional_historical_jd_ids'] == 1


def test_progress_hash_scope_same_for_relative_and_absolute_paths(fresh):
    data, old, seed, _, _ = fresh
    relative_seed = Path(os.path.relpath(seed))
    relative_old = Path(os.path.relpath(old))
    first = FreshLabelingStore(relative_seed, data, progress_for_input(relative_seed), output_for_input(relative_seed),
        old_benchmark=relative_old, min_rows=4, max_rows=4)
    assert first.summary()['reviewed'] == 0
    assert make_store(fresh).summary()['reviewed'] == 0
