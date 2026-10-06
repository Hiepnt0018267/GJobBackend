import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from evaluation.baseline_lexical import DEFAULT_THRESHOLD, LexicalBaseline, definition, tokens
from evaluation.benchmark_metrics import analyze
from evaluation.common import EvaluationDataError, make_pair_id
from evaluation.generate_pairs import DRAFT_FIELDS
from evaluation.labeling_store import atomic_csv
from evaluation.run_baseline_benchmark import compare, load_pairs, predict, sources, summarize, write_results, write_comparison


@pytest.fixture
def fixture(tmp_path, request):
    temporary = tempfile.TemporaryDirectory(prefix='baseline-fixture-', dir=tmp_path)
    request.addfinalizer(temporary.cleanup)
    fixture_root = Path(temporary.name)
    data = fixture_root / 'data'
    cv_text = 'Python backend developer builds APIs and SQL database applications. ' * 4
    jd_text = 'Python backend developer builds APIs and SQL database applications. ' * 2
    atomic_csv(data / 'Resume.csv', [{'ID': 'c1', 'Resume_str': cv_text, 'Resume_html': '', 'Category': 'IT'}], ['ID', 'Resume_str', 'Resume_html', 'Category'])
    atomic_csv(data / 'job_postings.csv', [{'job_id': 'j1', 'company_id': '', 'title': 'Python developer', 'description': jd_text, 'skills_desc': 'Python SQL'},
        {'job_id': 'j2', 'company_id': '', 'title': 'Nurse', 'description': 'Nursing clinical patient healthcare hospital. ' * 5, 'skills_desc': 'Nursing'}],
        ['job_id', 'company_id', 'title', 'description', 'skills_desc'])
    for name, fields in [('job_skills', ['job_id', 'skill_abr']), ('job_industries', ['job_id', 'industry_id']),
            ('companies', ['company_id', 'name']), ('company_industries', ['company_id', 'industry']),
            ('company_specialities', ['company_id', 'speciality']), ('benefits', ['job_id', 'type']), ('employee_counts', ['company_id', 'employee_count'])]:
        atomic_csv(data / (name + '.csv'), [], fields)
    rows = [dict.fromkeys(DRAFT_FIELDS, '') | dict(pair_id=make_pair_id('c1', jid), cv_id='c1', job_id=jid,
        pair_type='HARD_NEGATIVE_CANDIDATE', cv_source_row='2', job_source_row=str(i + 2), label=str(1 - i), label_reason='Human evidence.')
        for i, jid in enumerate(('j1', 'j2'))]
    path = fixture_root / 'labeled.csv'; atomic_csv(path, rows, DRAFT_FIELDS)
    return data, path


def test_frozen_normalization_and_formula():
    assert tokens('  PYTHON, C++ C#;  THE sql.  ') == ('python', 'c++', 'c#', 'sql')
    assert tokens('ＰＹＴＨＯＮ') == tokens('Python')
    assert tokens('mail@example.com https://example.com 123456') == ()
    assert DEFAULT_THRESHOLD == .5
    assert definition()['weights'] == {'tfidf_lexical_cosine': .7, 'title_token_coverage': .3}
    engine = LexicalBaseline({'cv': 'alpha beta', 'job': 'alpha gamma'})
    # N=2: alpha IDF=1, beta/gamma IDF=ln(3/2)+1. Equal term counts.
    import math
    lexical = 1 / (1 + (math.log(3 / 2) + 1) ** 2)
    assert engine.score('cv', 'job', 'alpha gamma') == pytest.approx(.7 * lexical + .3 * .5)
    assert engine.score('cv', 'cv', 'alpha beta') == pytest.approx(1.)
    assert LexicalBaseline({'cv': '', 'job': ''}).score('cv', 'job', '') == 0.
    assert engine.score('cv', 'job', 'senior director') == pytest.approx(.7 * lexical)  # no inferred seniority


def test_labels_sampling_and_categories_never_affect_score(fixture):
    data, path = fixture
    original = path.read_bytes()
    rows, validation = load_pairs(path, data, count=2)
    assert validation['rows'] == 2
    cvs, jobs, _ = sources(rows, data)
    first = predict(rows, cvs, jobs, .5)
    changed = [dict(r, label='0' if r['label'] == '1' else '1', label_reason='Different reason', pair_type='EASY_NEGATIVE_CANDIDATE', sampling_score='999', cv_category='OTHER') for r in rows]
    other_cvs, other_jobs, _ = sources(changed, data)
    assert (cvs, jobs) == (other_cvs, other_jobs)
    second = predict(changed, other_cvs, other_jobs, .5)
    assert [r['baseline_score'] for r in first] == [r['baseline_score'] for r in second]
    assert first == predict(list(reversed(rows)), cvs, jobs, .5)
    assert path.read_bytes() == original
    assert first[0]['pair_id'] == min(r['pair_id'] for r in rows)


@pytest.mark.parametrize('mutation', ['label', 'label_reason', 'duplicate'])
def test_invalid_labels_rejected(fixture, mutation):
    data, path = fixture
    with path.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    if mutation == 'duplicate':
        rows[1] = dict(rows[0])
    else:
        rows[0][mutation] = ''
    atomic_csv(path, rows, DRAFT_FIELDS)
    with pytest.raises(EvaluationDataError):
        load_pairs(path, data, count=2)


def test_comparison_exact_four_outcomes():
    baseline, semantic = [], []
    for i, (label, sp, bp, expected) in enumerate([(1, 1, 1, 'BOTH_CORRECT'), (0, 1, 1, 'BOTH_WRONG'),
            (1, 1, 0, 'SEMANTIC_ONLY_CORRECT'), (0, 1, 0, 'BASELINE_ONLY_CORRECT')]):
        row = dict(pair_id=f'p{i}', cv_id='c', job_id=f'j{i}', human_label=str(label), candidate_type='HARD_NEGATIVE_CANDIDATE', label_reason='Evidence')
        baseline.append(dict(row, baseline_score=float(bp), predicted_label=bp))
        semantic.append(dict(row, semantic_score=float(sp), predicted_label=str(sp)))
    stats, overlap = compare(semantic, baseline)
    assert list(stats['error_overlap'].values()) == [1, 1, 1, 1]
    assert [r['outcome_bucket'] for r in overlap] == ['BOTH_CORRECT', 'BOTH_WRONG', 'SEMANTIC_ONLY_CORRECT', 'BASELINE_ONLY_CORRECT']
    assert stats['hard_negative_head_to_head'] == {'human_negatives': 2, 'semantic_fp': 2, 'baseline_fp': 1, 'both_fp': 1, 'semantic_only_fp': 1, 'baseline_only_fp': 0}
    with pytest.raises(EvaluationDataError, match='ground truth'):
        compare([dict(r, human_label='1') for r in semantic], baseline)


def test_output_schema_and_shared_metric_semantic_compatibility(fixture, tmp_path, request):
    temporary = tempfile.TemporaryDirectory(prefix='baseline-output-', dir=tmp_path)
    request.addfinalizer(temporary.cleanup)
    tmp_path = Path(temporary.name)
    data, path = fixture
    rows, _ = load_pairs(path, data, count=2)
    cvs, jobs, _ = sources(rows, data)
    predictions = predict(rows, cvs, jobs, .5)
    metrics, thresholds = summarize(predictions, .5)
    semantic_view = [dict(r, semantic_score=r['baseline_score']) for r in predictions]
    assert metrics['overall'] == analyze(semantic_view, .5)
    metrics.update(definition=definition(), reproducibility={})
    out = tmp_path / 'results'; write_results(out, predictions, metrics, thresholds)
    assert {p.name for p in out.iterdir()} == {'report.md', 'metrics.json', 'predictions.csv', 'threshold_analysis.csv', 'false_positives.csv', 'false_negatives.csv', 'hard_negative_errors.csv'}
    with (out / 'predictions.csv').open() as handle:
        assert 'baseline_score' in next(csv.reader(handle))
    assert 'Resume_str' not in (out / 'report.md').read_text()
    stats, overlap = compare(semantic_view, predictions)
    comparison = tmp_path / 'comparison'
    write_comparison(comparison, metrics, metrics, stats, overlap)
    assert {p.name for p in comparison.iterdir()} == {'semantic_vs_baseline.md', 'semantic_vs_baseline.json', 'error_overlap.csv'}
    assert 'Hard-negative FP' in (comparison / 'semantic_vs_baseline.md').read_text()


def test_no_app_database_llm_embedding_or_network_imports():
    code = "import sys,socket; socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network forbidden')); import evaluation.run_baseline_benchmark; from evaluation.baseline_lexical import LexicalBaseline; assert LexicalBaseline({'c':'python','j':'python'}).score('c','j','python')==1.; assert not any(m.startswith(('app.', 'sqlalchemy', 'httpx')) for m in sys.modules)"
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
