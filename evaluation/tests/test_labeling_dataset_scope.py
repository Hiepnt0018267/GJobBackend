from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from evaluation.common import EvaluationDataError, make_pair_id
from evaluation.generate_pairs import DRAFT_FIELDS
from evaluation.labeling_app import create_app, main, progress_for_input
from evaluation.labeling_store import LabelingStore, PROGRESS_FIELDS, atomic_csv


@pytest.fixture
def datasets(tmp_path):
    data = tmp_path / 'sources'
    atomic_csv(data / 'Resume.csv', [{'ID': 'c1', 'Category': 'IT', 'Resume_str': 'Python API developer'}],
               ['ID', 'Category', 'Resume_str'])
    atomic_csv(data / 'job_postings.csv', [dict(job_id=f'j{i}', title='Engineer', description='Python API requirements')
               for i in range(610)], ['job_id', 'title', 'description'])

    def pair(i):
        return dict.fromkeys(DRAFT_FIELDS, '') | dict(pair_id=make_pair_id('c1', f'j{i}'),
            cv_id='c1', job_id=f'j{i}', pair_type='POSITIVE_CANDIDATE')

    def decision(row):
        return dict.fromkeys(PROGRESS_FIELDS, '') | {key: row[key] for key in ('pair_id', 'cv_id', 'job_id')} | dict(
            human_label='0', human_reason='Preserved human reason.', review_status='REVIEWED', reviewed_at='2026-01-01T00:00:00Z')

    old = tmp_path / 'evaluation_pairs_draft.csv'
    legacy = tmp_path / 'evaluation_labeling_progress.csv'
    seed = tmp_path / 'evaluation_pairs_benchmark_seed.csv'
    old_rows = [pair(i) for i in range(400)]
    atomic_csv(old, old_rows, DRAFT_FIELDS)
    atomic_csv(legacy, [decision(r) for r in old_rows[:78]], PROGRESS_FIELDS)
    seed_rows = [pair(i) | decision(pair(i)) for i in range(10)] + [pair(i) for i in range(400, 610)]
    atomic_csv(seed, seed_rows, list(dict.fromkeys(DRAFT_FIELDS + PROGRESS_FIELDS)))
    return data, old, legacy, seed, tmp_path / 'labeled.csv'


@pytest.mark.parametrize('active,expected', [('old', (400, 78, 322)), ('seed', (220, 10, 210))])
def test_authoritative_pair_counts(datasets, active, expected):
    data, old, legacy, seed, output = datasets
    store = LabelingStore(old if active == 'old' else seed, data,
                          legacy if active == 'old' else progress_for_input(seed), output)
    client = TestClient(create_app(store, SimpleNamespace(model='not-called')))
    state = client.get('/review/state').json()
    assert tuple(state[k] for k in ('total', 'reviewed', 'remaining')) == expected
    assert len(state['pairs']) == expected[0]


def test_switching_inputs_never_reuses_legacy_progress(datasets):
    data, old, legacy, seed, output = datasets
    legacy_bytes = legacy.read_bytes()
    seed_bytes = seed.read_bytes()
    assert progress_for_input(seed).name == 'evaluation_labeling_progress_benchmark_seed.csv'
    assert progress_for_input(old) != progress_for_input(seed) != legacy
    store = LabelingStore(seed, data, progress_for_input(seed), output)
    pid = store.rows[10]['pair_id']
    store.review(pid, '1', 'New human review.')
    resumed = LabelingStore(seed, data, progress_for_input(seed), output)
    assert resumed.summary()['reviewed'] == 11 and resumed.summary()['remaining'] == 209
    assert resumed.state(pid)['human_label'] == '1'
    assert legacy.read_bytes() == legacy_bytes and seed.read_bytes() == seed_bytes
    assert LabelingStore(old, data, legacy, output).summary()['reviewed'] == 78
    with pytest.raises(EvaluationDataError, match='different input dataset'):
        LabelingStore(seed, data, legacy, output)
    assert legacy.read_bytes() == legacy_bytes


def test_unreviewed_cache_cannot_erase_embedded_decisions(datasets):
    data, _, _, seed, output = datasets
    store = LabelingStore(seed, data, progress_for_input(seed), output)
    embedded = store.state(store.rows[0]['pair_id'])
    blank = dict.fromkeys(PROGRESS_FIELDS, '') | {k: embedded[k] for k in ('pair_id', 'cv_id', 'job_id')} | dict(review_status='UNREVIEWED')
    atomic_csv(progress_for_input(seed), [blank], PROGRESS_FIELDS)
    reopened = LabelingStore(seed, data, progress_for_input(seed), output)
    assert reopened.state(embedded['pair_id']) == embedded
    assert reopened.summary()['reviewed'] == 10


def test_cli_uses_input_and_reports_actual_dataset(datasets, monkeypatch, capsys):
    import uvicorn
    data, _, _, seed, output = datasets
    apps = []
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kwargs: apps.append(app))
    main(['--input', str(seed), '--data-dir', str(data), '--output', str(output)])
    state = TestClient(apps[0]).get('/review/state').json()
    assert (state['total'], state['reviewed'], state['remaining']) == (220, 10, 210)
    startup = capsys.readouterr().out
    assert str(seed.resolve()) in startup
    assert 'Reviewed: 10 / 220; Remaining: 210' in startup


def test_cli_requires_explicit_input():
    with pytest.raises(SystemExit) as exc:
        main(['--data-dir', 'unused'])
    assert exc.value.code == 2
