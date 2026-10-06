import asyncio
import csv
from types import SimpleNamespace

import pytest

from evaluation.benchmark_metrics import classification, ranking, errors
from evaluation.common import EvaluationDataError
from evaluation.generate_pairs import DRAFT_FIELDS
from evaluation.labeling_store import atomic_csv
from evaluation.run_semantic_benchmark import CachedVectors, context_provider, load_benchmark, prepare_sources, score_pairs, summarize, write_reports
from evaluation.tests.test_hard_generation import source


@pytest.fixture
def labeled(source, tmp_path):
    data, rows, _ = source
    for row, label in zip(rows, ('1', '0', '1')):
        row.update(label=label, label_reason='Human evidence only; never scoring input.')
    path = tmp_path / 'labeled.csv'
    atomic_csv(path, rows, DRAFT_FIELDS)
    return data, path


def test_valid_input_and_deterministic_order(labeled):
    data, path = labeled
    original = path.read_bytes()
    rows, result = load_benchmark(path, data, expected_count=3)
    assert result == {'rows': 3, 'label_0': 1, 'label_1': 2}
    assert [r['pair_id'] for r in rows] == sorted(r['pair_id'] for r in rows)
    assert path.read_bytes() == original
    with pytest.raises(EvaluationDataError, match='Expected 220'):
        load_benchmark(path, data)


@pytest.mark.parametrize('mutation', ['missing_label', 'missing_reason', 'duplicate'])
def test_invalid_benchmark_rejected_before_embedding(labeled, mutation):
    data, path = labeled
    with path.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    if mutation == 'duplicate':
        rows[1] = dict(rows[0])
    else:
        rows[0]['label' if mutation == 'missing_label' else 'label_reason'] = ''
    atomic_csv(path, rows, DRAFT_FIELDS)
    with pytest.raises(EvaluationDataError):
        load_benchmark(path, data, expected_count=3)


def test_known_metrics_and_ties():
    result = classification([1, 0, 1, 0], [.9, .8, .4, .1], .5)
    assert [result[k] for k in ('TP', 'TN', 'FP', 'FN')] == [1, 1, 1, 1]
    assert all(result[k] == .5 for k in ('precision', 'recall', 'f1', 'accuracy', 'specificity'))
    ranks = ranking([1, 0, 1, 0], [.9, .8, .4, .1])
    assert ranks['roc_auc'] == .75
    assert ranks['average_precision'] == pytest.approx(5 / 6)
    assert ranking([0, 1], [.5, .5]) == {'roc_auc': .5, 'average_precision': .5}
    assert ranking([0, 0], [.5, .6]) == {'roc_auc': None, 'average_precision': None}
    assert classification([1], [.5], .5)['TP'] == 1


class FakeProvider:
    def __init__(self):
        self.calls = []

    async def embed_many(self, texts):
        from app.embeddings.base import EmbeddingBatchResult
        self.calls.append(list(texts))
        return EmbeddingBatchResult(tuple((1., .5 if 'Java' in t else 1.) for t in texts), 'fake', 'synthetic', 2)


def test_existing_service_cache_mapping_no_db_or_llm(labeled, tmp_path, monkeypatch):
    import httpx
    from sqlalchemy.engine import Engine
    monkeypatch.setattr(Engine, 'connect', lambda *a, **k: pytest.fail('DB access forbidden'))
    monkeypatch.setattr(httpx.AsyncClient, '__init__', lambda *a, **k: pytest.fail('Real network forbidden'))
    data, path = labeled
    rows, _ = load_benchmark(path, data, expected_count=3)
    cvs, jobs, _ = prepare_sources(rows, data)
    fake = FakeProvider()
    cache = CachedVectors(fake, tmp_path / 'cache', {'model': 'synthetic', 'digest': 'v1'})
    asyncio.run(cache.preload(cvs, jobs, 2))
    predictions = asyncio.run(score_pairs(rows, cvs, jobs, cache, .5))
    assert [p['pair_id'] for p in predictions] == [r['pair_id'] for r in rows]
    assert cache.misses == 6 and cache.hits == 0
    changed = [dict(r, label='0', label_reason='New human reason', pair_type='EASY_NEGATIVE_CANDIDATE', sampling_score='999') for r in rows]
    changed_cvs, changed_jobs, _ = prepare_sources(changed, data)
    assert (changed_cvs, changed_jobs) == (cvs, jobs)
    rescored = asyncio.run(score_pairs(changed, cvs, jobs, cache, .5))
    assert [p['semantic_score'] for p in rescored] == [p['semantic_score'] for p in predictions]
    assert all('Human evidence' not in t and 'New human' not in t and '999' not in t for batch in fake.calls for t in batch)
    cached = CachedVectors(fake, tmp_path / 'cache', cache.identity)
    count = len(fake.calls)
    asyncio.run(cached.preload(cvs, jobs, 2))
    assert cached.hits == 6 and cached.misses == 0 and len(fake.calls) == count
    revised = dict(cvs); revised[next(iter(revised))] += '\nA new professional skill'
    fresh = CachedVectors(fake, tmp_path / 'cache', cache.identity)
    asyncio.run(fresh.preload(revised, jobs, 2))
    assert fresh.hits == 5 and fresh.misses == 1
    model_changed = CachedVectors(fake, tmp_path / 'cache', {'model': 'synthetic', 'digest': 'v2'})
    asyncio.run(model_changed.preload(cvs, jobs, 2))
    assert model_changed.misses == 6
    with pytest.raises(EvaluationDataError, match='model does not match'):
        cached.accept({'model': 'wrong-model', 'provider': 'fake', 'dimensions': 2, 'vector': [1., 2.]}, 'text')


def test_error_reports_groups_and_thresholds(tmp_path):
    rows = [dict(pair_id=f'p{i}', cv_id='c', job_id=f'j{i}', human_label=str(label), semantic_score=score,
        predicted_label=int(score >= .5), candidate_type=kind, label_reason='Human explanation.')
        for i, (label, score, kind) in enumerate([(1, .9, 'POSITIVE_CANDIDATE'),
            (0, .8, 'HARD_NEGATIVE_CANDIDATE'), (1, .4, 'HARD_NEGATIVE_CANDIDATE'), (0, .1, 'EASY_NEGATIVE_CANDIDATE')])]
    metrics, thresholds = summarize(rows, .5)
    assert metrics['groups']['HARD_NEGATIVE_CANDIDATE']['human_positive'] == 1
    assert metrics['groups']['HARD_NEGATIVE_CANDIDATE']['false_positive_rate'] == 1
    assert [r['pair_id'] for r in errors(rows, 0)] == ['p1']
    assert [r['pair_id'] for r in errors(rows, 1)] == ['p2']
    assert any(r['threshold'] == .5 for r in thresholds)
    metrics['reproducibility'] = {'model': 'fake'}
    write_reports(tmp_path, rows, metrics, thresholds)
    assert len(list(tmp_path.iterdir())) == 7
    report = (tmp_path / 'report.md').read_text()
    assert 'in-sample exploratory' in report
    assert 'No weighted title/skills rules' in report


def test_offline_context_adapter_contract(monkeypatch):
    import httpx
    original = httpx.AsyncClient
    def handler(request):
        import json
        assert request.url.path == '/api/embed'
        body = json.loads(request.content)
        assert body == {'model': 'bge-m3', 'input': ['synthetic source'], 'truncate': False, 'options': {'num_ctx': 8192, 'num_batch': 8192}}
        return httpx.Response(200, json={'model': 'bge-m3', 'embeddings': [[1., 2.]]})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))
    result = asyncio.run(context_provider('http://localhost:11434', 'bge-m3', 30, 8192).embed_many(['synthetic source']))
    assert result.vectors == ((1., 2.),)
