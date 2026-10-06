import csv
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from evaluation.common import EvaluationDataError, make_pair_id
from evaluation.labeling_ai import LabelingAI, parse_suggestion
from evaluation.labeling_app import create_app
from evaluation.labeling_store import LabelingStore
from evaluation.validate_labels import REQUIRED_DRAFT_FIELDS, validate_labeled_file


def write(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(rows)


@pytest.fixture
def store(tmp_path):
    root = tmp_path / 'data'; root.mkdir()
    write(root / 'Resume.csv', ['ID', 'Resume_str', 'Resume_html', 'Category'],
          [{'ID': 'c1', 'Resume_str': 'Python API experience, PRIVATE RAW CV', 'Resume_html': '', 'Category': 'IT'}])
    write(root / 'job_postings.csv', ['job_id', 'company_id', 'title', 'description'],
          [{'job_id': j, 'company_id': '', 'title': 'Engineer', 'description': 'Python API requirements, PRIVATE RAW JD'} for j in ['j1', 'j2']])
    for name, fields in [('job_skills.csv', ['job_id', 'skill_abr']), ('job_industries.csv', ['job_id', 'industry_id']),
                         ('companies.csv', ['company_id', 'name']), ('company_industries.csv', ['company_id', 'industry']),
                         ('company_specialities.csv', ['company_id', 'speciality']), ('benefits.csv', ['job_id', 'type']),
                         ('employee_counts.csv', ['company_id', 'employee_count'])]:
        write(root / name, fields, [])
    rows = []
    for job in ['j2', 'j1']:
        r = dict.fromkeys(sorted(REQUIRED_DRAFT_FIELDS), '')
        r.update(pair_id=make_pair_id('c1', job), cv_id='c1', job_id=job, pair_type='HARD_NEGATIVE_CANDIDATE',
                 cv_category='IT', job_title='Engineer', sampling_score='0.2', cv_source_row='2', job_source_row='2',
                 cv_text_preview='PRIVATE RAW CV', job_text_preview='PRIVATE RAW JD')
        rows.append(r)
    draft = tmp_path / 'draft.csv'; write(draft, sorted(REQUIRED_DRAFT_FIELDS), rows)
    return LabelingStore(draft, root, tmp_path / 'progress.csv', tmp_path / 'labeled.csv')


def test_draft_sources_and_order(store):
    assert [r['job_id'] for r in store.rows] == ['j2', 'j1']
    pair = store.pair(store.rows[0]['pair_id'])
    assert 'PRIVATE RAW CV' in pair['cv']['text']
    assert 'PRIVATE RAW JD' in pair['job']['text']
    assert store.summary()['resume_index'] == 0


@pytest.mark.parametrize('content', ['{}', '{bad', '{"suggested_label":true,"reason":"yes"}',
    '{"suggested_label":2,"reason":"no"}', '{"suggested_label":1,"reason":"   "}',
    '{"suggested_label":1,"reason":null}', '{"suggested_label":1,"reason":42}'])
def test_invalid_ai(content):
    with pytest.raises(EvaluationDataError):
        parse_suggestion(content)


def test_mock_ollama_contract_and_bias_exclusion(store):
    def handler(request):
        payload = json.loads(request.content)
        assert payload['think'] is False and payload['stream'] is False
        assert payload['options']['temperature'] == 0
        system = payload['messages'][0]['content']
        assert 'The `reason` field MUST be written entirely in Vietnamese.' in system
        assert 'Do not answer the reason in English.' in system
        assert 'Use concise, natural Vietnamese' in system
        assert '1-2 short sentences' in system
        assert 'only on professional fit evidence from the CV and JD' in system
        assert 'Do not include names, emails, phone numbers, addresses' in system
        evidence = json.loads(payload['messages'][1]['content'])
        assert set(evidence) == {'cv_text', 'jd_title', 'jd_description'}
        assert 'sampling_score' not in request.content.decode()
        return httpx.Response(200, json={'message': {'content': json.dumps({'suggested_label': 1, 'reason': 'Kinh nghiệm Python và API trong CV phù hợp với yêu cầu công việc.'})}})
    ai = LabelingAI('http://localhost:11434', 'qwen3:8b', 'Holistic relevance rubric', httpx.MockTransport(handler))
    pair = store.pair(store.rows[0]['pair_id'])
    result = ai.suggest(pair['cv'], pair['job'])
    assert result.suggested_label == 1
    assert result.reason == 'Kinh nghiệm Python và API trong CV phù hợp với yêu cầu công việc.'


@pytest.mark.parametrize('url', ['https://example.com', 'http://example.com', 'http://localhost@evil.com', 'http://localhost/path'])
def test_remote_provider_rejected(url):
    with pytest.raises(EvaluationDataError):
        LabelingAI(url, 'qwen3:8b', '')


@pytest.mark.parametrize('code', [404, 500])
def test_ollama_failure(code, store):
    ai = LabelingAI('http://localhost:11434', 'qwen3:8b', '', httpx.MockTransport(lambda r: httpx.Response(code)))
    pair = store.pair(store.rows[0]['pair_id'])
    with pytest.raises(EvaluationDataError):
        ai.suggest(pair['cv'], pair['job'])
    assert store.summary()['reviewed'] == 0


def test_ai_separate_autosave_resume_and_human_disagreement(store):
    pid = store.rows[0]['pair_id']
    store.suggestion(pid, 1, 'AI reason', 'qwen3:8b')
    assert store.state(pid)['human_label'] == ''
    assert store.state(pid)['review_status'] == 'UNREVIEWED'
    store.review(pid, '0', 'Core capabilities do not match.')
    store.suggestion(pid, 1, 'Regenerated reason', 'qwen3:8b')
    assert store.state(pid)['human_label'] == '0'
    assert store.state(pid)['human_reason'] == 'Core capabilities do not match.'
    reloaded = LabelingStore(store.progress_path.parent / 'draft.csv', store.data_dir, store.progress_path, store.output_path)
    assert reloaded.state(pid) == store.state(pid)
    assert reloaded.summary()['resume_index'] == 1
    text = store.progress_path.read_text()
    assert 'PRIVATE RAW' not in text


@pytest.mark.parametrize('label,reason', [('2','reason'), ('','reason'), ('1',' '), ('0','')])
def test_human_validation(store, label, reason):
    with pytest.raises(EvaluationDataError):
        store.review(store.rows[0]['pair_id'], label, reason)
    assert store.summary()['reviewed'] == 0


def test_export_blocked_then_valid_and_private(store):
    with pytest.raises(EvaluationDataError):
        store.export()
    assert not store.output_path.exists()
    for row in store.rows:
        row['untrusted_extra_raw_text'] = 'PRIVATE RAW EXTRA COLUMN'
        store.review(row['pair_id'], '0', 'Human-reviewed role mismatch.')
    assert store.export()['validation'] == 'PASS'
    text = store.output_path.read_text()
    assert 'PRIVATE RAW' not in text and 'ai_reason' not in text
    assert 'untrusted_extra_raw_text' not in text
    assert validate_labeled_file(store.output_path, store.output_path.parent / 'final.csv', data_dir=store.data_dir)['rows'] == 2
    with pytest.raises(EvaluationDataError):
        validate_labeled_file(store.output_path, store.output_path.parent / 'bad.csv')


def test_duplicate_draft_rejected(store):
    draft = store.progress_path.parent / 'draft.csv'
    write(draft, list(store.rows[0]), [store.rows[0], store.rows[0]])
    with pytest.raises(EvaluationDataError, match='duplicate'):
        LabelingStore(draft, store.data_dir, store.progress_path, store.output_path)


def test_api_local_session_and_save(store):
    ai = LabelingAI('http://localhost:11434', 'qwen3:8b', '', httpx.MockTransport(lambda r: httpx.Response(200, json={'message': {'content': '{"suggested_label":1,"reason":"Relevant skills"}'}})))
    client = TestClient(create_app(store, ai))
    html = client.get('/').text
    token = html.split("const token='")[1].split("'")[0]
    pid = store.rows[0]['pair_id']
    assert client.post(f'/review/pairs/{pid}/decision', json={'label':'0','reason':'Mismatch'}).status_code == 403
    headers = {'x-review-token': token}
    assert client.post(f'/review/pairs/{pid}/suggestion', headers=headers, json={}).status_code == 200
    assert store.state(pid)['human_label'] == ''
    assert client.post(f'/review/pairs/{pid}/decision', headers=headers, json={'label':'0','reason':'Mismatch'}).status_code == 200
    assert client.post('/review/export', headers=headers, json={}).status_code == 400


def test_regeneration_calls_ollama_and_replaces_only_ai_fields(store):
    pid = store.rows[0]['pair_id']
    store.suggestion(pid, 1, 'Previously cached English reason.', 'qwen3:8b')
    store.review(pid, '1', 'Lý do riêng của người review.')
    before = store.state(pid)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'message': {'content': json.dumps({
            'suggested_label': 0, 'reason': 'CV chưa thể hiện kỹ năng cốt lõi được yêu cầu trong JD.'
        })}})
    ai = LabelingAI('http://localhost:11434', 'qwen3:8b', '', httpx.MockTransport(handler))
    client = TestClient(create_app(store, ai))
    token = client.get('/').text.split("const token='")[1].split("'")[0]
    response = client.post(f'/review/pairs/{pid}/suggestion', headers={'x-review-token': token}, json={})
    assert response.status_code == 200
    assert len(calls) == 1
    after = store.state(pid)
    assert after['ai_suggested_label'] == '0'
    assert after['ai_reason'] == 'CV chưa thể hiện kỹ năng cốt lõi được yêu cầu trong JD.'
    for field in ('human_label', 'human_reason', 'review_status', 'reviewed_at'):
        assert after[field] == before[field]
    reloaded = LabelingStore(store.progress_path.parent / 'draft.csv', store.data_dir, store.progress_path, store.output_path)
    assert reloaded.state(pid) == after


def test_startup_preserves_cached_english_suggestion(store):
    pid = store.rows[0]['pair_id']
    store.suggestion(pid, 1, 'Existing English suggestion stays cached.', 'qwen3:8b')
    before = store.progress_path.read_bytes()
    reloaded = LabelingStore(store.progress_path.parent / 'draft.csv', store.data_dir, store.progress_path, store.output_path)
    assert reloaded.state(pid)['ai_reason'] == 'Existing English suggestion stays cached.'
    assert store.progress_path.read_bytes() == before


@pytest.mark.parametrize('error', [httpx.ConnectError, httpx.ReadTimeout])
def test_connection_timeout_preserve_review(store, error):
    pid = store.rows[0]['pair_id']
    store.review(pid, '0', 'Human judgment persists.')
    def handler(request):
        raise error('Synthetic failure', request=request)
    ai = LabelingAI('http://localhost:11434', 'qwen3:8b', '', httpx.MockTransport(handler))
    p = store.pair(pid)
    with pytest.raises(EvaluationDataError):
        ai.suggest(p['cv'], p['job'])
    assert store.state(pid)['human_label'] == '0'


def test_failed_atomic_save_preserves_previous_decision(store, monkeypatch):
    pid = store.rows[0]['pair_id']
    store.review(pid, '0', 'Original human reason.')
    def fail():
        raise OSError('Synthetic disk error')
    monkeypatch.setattr(store, 'persist', fail)
    with pytest.raises(OSError):
        store.review(pid, '1', 'Updated reason.')
    assert store.state(pid)['human_label'] == '0'
    assert store.state(pid)['human_reason'] == 'Original human reason.'
