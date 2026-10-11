import csv
import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evaluation.common import EvaluationDataError
from evaluation.labeling_app import create_app, progress_for_input, output_for_input
from evaluation.labeling_store import atomic_csv
from evaluation.ranking_dataset import FIELDS, generate, sources, sha, validate, case_id
from evaluation.ranking_labeling import RankingLabelingStore


@pytest.fixture
def ranking(tmp_path):
    data = tmp_path / 'sources'
    data.mkdir()
    cv_rows = []
    texts = ['python django server api sql backend developer web',
             'software javascript web developer programming',
             'react angular vue css ui frontend api sql backend',
             'nurse patient clinical healthcare hospital surgical']
    for group, text in enumerate(texts):
        for i in range(3):
            cv_rows.append({'ID': f'c{group}{i}', 'Resume_str': (text+' ') * 12 + f'uniqueidentifier{group}{i}'})
    atomic_csv(data/'Resume.csv', cv_rows, ['ID', 'Resume_str'])
    job_rows = [{'job_id': f'j{i}', 'title': 'Python backend developer',
                 'description': ('python django api backend sql developer software web ') * 10 + marker,
                 'skills_desc': ''} for i, marker in enumerate(['alphaposting', 'betaposting'])]
    atomic_csv(data/'job_postings.csv', job_rows, ['job_id', 'title', 'description', 'skills_desc'])
    cvs, jobs, hashes = sources(data)
    rows, _ = generate(cvs, jobs, hashes['job_postings.csv'], job_count=2)
    seed = tmp_path/'ranking_pairs_seed.csv'
    atomic_csv(seed, rows, FIELDS)
    manifest = tmp_path/'seed_manifest.json'
    manifest.write_text(json.dumps({'seed_sha256': sha(seed), 'source_hashes': hashes}), encoding='utf-8')
    return tmp_path, data, seed, manifest, rows, cvs, jobs


def store(fixture):
    root, data, seed, manifest, *_ = fixture
    return RankingLabelingStore(seed, data, root/'ranking_labeling_progress.csv',
                                root/'ranking_pairs_labeled.csv', manifest)


def test_determinism_stable_ids_and_pool_composition(ranking):
    _, _, _, _, rows, cvs, jobs = ranking
    one, info = generate(cvs, jobs, 'sourcehash', job_count=2)
    two, _ = generate(dict(reversed(list(cvs.items()))), dict(reversed(list(jobs.items()))), 'sourcehash', job_count=2)
    assert one == two
    assert len(one) == 20 and info['max_cv_reuse'] <= 2
    assert case_id('j0', 'sourcehash') == case_id('j0', 'sourcehash')
    assert all(r['relevance_grade'] == r['relevance_reason'] == '' for r in rows)
    assert validate(rows, cvs, jobs)['cases'] == 2


@pytest.mark.parametrize('mutation', ['duplicate', 'ref', 'case', 'small', 'position', 'missing_cv', 'blank'])
def test_invalid_pools_rejected(ranking, mutation):
    _, _, _, _, original, cvs, jobs = ranking
    rows = [dict(r) for r in original]
    if mutation == 'duplicate': rows.append(dict(rows[0]))
    elif mutation == 'ref': rows[0]['candidate_source_ref'] = '999'
    elif mutation == 'case': rows[0]['ranking_case_id'] = rows[-1]['ranking_case_id']
    elif mutation == 'small': rows = rows[:1]
    elif mutation == 'position': rows[0]['pool_position_seed'] = '999'
    elif mutation == 'missing_cv': rows[0]['cv_id'] = 'unknown'
    elif mutation == 'blank': cvs[rows[0]['cv_id']]['text'] = ''
    with pytest.raises(EvaluationDataError): validate(rows, cvs, jobs)


@pytest.mark.parametrize('grade', ['', '-1', '3', 'good', 'UNSURE'])
def test_invalid_grades(ranking, grade):
    review = store(ranking)
    with pytest.raises(EvaluationDataError): review.review(ranking[4][0]['pair_id'], grade, 'Evidence')


def test_export_coverage_resume_and_freeze(ranking):
    root, _, _, _, rows, cvs, jobs = ranking
    review = store(ranking)
    assert review.summary()['reviewed'] == 0
    assert not review.progress_path.exists()
    with pytest.raises(EvaluationDataError): review.export()
    for i, row in enumerate(rows): review.review(row['pair_id'], str(i % 3), 'Professional evidence')
    resumed = store(ranking)
    assert resumed.summary()['reviewed'] == 20
    exported = resumed.export()
    assert exported['rows'] == 20
    final = list(csv.DictReader(resumed.output_path.open(encoding='utf-8')))
    assert [(r['pair_id'], r['relevance_grade'], r['relevance_reason']) for r in final] == [
        (r['pair_id'], str(i % 3), 'Professional evidence') for i, r in enumerate(rows)]
    assert validate(final, cvs, jobs, labeled=True)['rows'] == 20
    assert json.loads((root/'dataset_summary.json').read_text())['frozen']
    with pytest.raises(EvaluationDataError): resumed.review(rows[0]['pair_id'], '0', 'Correction')


def test_progress_hash_isolation_and_stale_session(ranking):
    first, stale = store(ranking), store(ranking)
    pid = ranking[4][0]['pair_id']
    first.review(pid, '1', 'Transferable evidence')
    with pytest.raises(EvaluationDataError): stale.review(pid, '2', 'Other evidence')
    records = list(csv.DictReader(first.progress_path.open(encoding='utf-8')))
    records[0]['seed_sha256'] = 'different'
    atomic_csv(first.progress_path, records, list(records[0]))
    with pytest.raises(EvaluationDataError): store(ranking)


@pytest.mark.parametrize('grade,flags', [('0', ['ALL_SAME_GRADE', 'NO_RELEVANT_CANDIDATE']),
                                       ('2', ['ALL_SAME_GRADE', 'NO_NEGATIVE'])])
def test_quality_flags_not_drop(ranking, grade, flags):
    rows = [dict(r, relevance_grade=grade, relevance_reason='Evidence') for r in ranking[4]]
    result = validate(rows, ranking[5], ranking[6], labeled=True)
    assert result['rows'] == 20
    assert all(p['flags'] == flags for p in result['pools'].values())


def test_blind_payload_ui_and_old_progress_guard(ranking):
    review = store(ranking)
    client = TestClient(create_app(review, None))
    home = client.get('/')
    assert home.status_code == 200
    for forbidden in ['semantic_score', 'baseline_score', 'hybrid_score', 'candidate_type', 'model rank', 'suggested_label']:
        assert forbidden not in home.text
        assert forbidden not in json.dumps(client.get('/review/state').json())
        assert forbidden not in json.dumps(client.get('/review/pairs/'+ranking[4][0]['pair_id']).json())
    assert 'data-grade="2"' in home.text
    assert client.post('/review/pairs/'+ranking[4][0]['pair_id']+'/decision', json={'label':'2','reason':'Evidence'}).status_code == 403
    with pytest.raises(EvaluationDataError):
        RankingLabelingStore(ranking[2], ranking[1], ranking[0]/'evaluation_labeling_progress.csv',
                            ranking[0]/'evaluation_pairs_labeled.csv', ranking[3])
    assert progress_for_input(ranking[2]).name == 'ranking_labeling_progress.csv'
    assert output_for_input(ranking[2]).name == 'ranking_pairs_labeled.csv'


def test_empty_reason_and_source_change(ranking):
    review = store(ranking)
    with pytest.raises(EvaluationDataError): review.review(ranking[4][0]['pair_id'], '1', '  ')
    source = ranking[1]/'Resume.csv'
    source.write_bytes(source.read_bytes()+b'\n')
    with pytest.raises(EvaluationDataError): store(ranking)


def test_generator_no_matcher_or_prediction_imports():
    module = importlib.import_module('evaluation.ranking_dataset')
    text = Path(module.__file__).read_text(encoding='utf-8')
    for forbidden in ['SemanticMatchingService', 'baseline_lexical', 'hybrid_protocol', 'predictions.csv', 'httpx', 'app.services']:
        assert forbidden not in text


def test_preexisting_session_cannot_mutate_after_other_session_freezes(ranking):
    review = store(ranking)
    for row in ranking[4]: review.review(row['pair_id'], '1', 'Evidence')
    stale = store(ranking)
    review.export()
    before = sha(review.output_path)
    with pytest.raises(EvaluationDataError): stale.review(ranking[4][0]['pair_id'], '2', 'Correction')
    with pytest.raises(EvaluationDataError): stale.export()
    assert sha(review.output_path) == before


def test_process_write_lock_blocks_safely(ranking):
    review = store(ranking)
    lock_path = review.progress_path.with_suffix('.lock')
    lock_path.write_text('synthetic competing process', encoding='utf-8')
    with pytest.raises(EvaluationDataError): review.review(ranking[4][0]['pair_id'], '0', 'Evidence')
    assert not review.progress_path.exists() and lock_path.exists()
