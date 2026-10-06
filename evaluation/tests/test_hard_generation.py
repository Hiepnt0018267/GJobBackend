import csv
import hashlib
from pathlib import Path

import pytest

from evaluation.common import make_pair_id
from evaluation.generate_pairs import DRAFT_FIELDS
from evaluation.generate_hard_pairs import archive_exact, main, mine, reviewed_records
from evaluation.labeling_store import PROGRESS_FIELDS, LabelingStore, atomic_csv


@pytest.fixture
def source(tmp_path):
    data = tmp_path / 'data'; data.mkdir()
    cv_text = 'Backend Python developer builds API server django applications and database sql queries. Software programming web deployment linux cloud. '
    cvs = [{'ID': f'c{i}', 'Category': 'INFORMATION-TECHNOLOGY', 'Resume_html': '',
            'Resume_str': cv_text * 3 + f'Career achievement {chr(97+i)}.'} for i in range(6)]
    atomic_csv(data/'Resume.csv', cvs, list(cvs[0]))
    jobs = []
    for i, (title, body) in enumerate([
        ('Python Backend Developer', cv_text + 'Maintain backend server applications.'),
        ('Python API Engineer', cv_text + 'Build python django API integrations.'),
        ('Java Backend Developer', 'Java spring backend server api software programming web applications database sql linux cloud. Build scalable backend systems.'),
        ('React Frontend Developer', 'React javascript frontend css html ui software programming web applications database sql api linux cloud. Build browser interfaces.'),
        ('Registered Nurse', 'Clinical nurse nursing patient medical healthcare hospital surgical therapy clinical care patient monitoring.'),
        ('School Teacher', 'Teacher teaching classroom curriculum education school instructor student educator school pedagogy teaching lessons.'),
    ]):
        jobs.append({'job_id':f'j{i}', 'company_id':'', 'title':title, 'description':body,
                     'skills_desc':'', 'formatted_experience_level':'Entry level'})
    atomic_csv(data/'job_postings.csv', jobs, list(jobs[0]))
    for name, fields in [('job_skills',['job_id','skill_abr']), ('job_industries',['job_id','industry_id']),
                         ('companies',['company_id','name']), ('company_industries',['company_id','industry']),
                         ('company_specialities',['company_id','speciality']), ('benefits',['job_id','type']),
                         ('employee_counts',['company_id','employee_count'])]:
        atomic_csv(data/(name+'.csv'), [], fields)
    old = []
    for cid,jid in [('c0','j0'),('c1','j2'),('c2','j4')]:
        r=dict.fromkeys(DRAFT_FIELDS,'')
        r.update(pair_id=make_pair_id(cid,jid),cv_id=cid,job_id=jid,pair_type='HARD_NEGATIVE_CANDIDATE',
                 cv_category='INFORMATION-TECHNOLOGY',job_title=jobs[int(jid[1:])]['title'],cv_source_row='2',job_source_row='2')
        old.append(r)
    reviews = {r['pair_id']:dict.fromkeys(PROGRESS_FIELDS,'') | {
        'pair_id':r['pair_id'],'cv_id':r['cv_id'],'job_id':r['job_id'],'human_label':'0',
        'human_reason':'Original human decision preserved exactly.','review_status':'REVIEWED','reviewed_at':'2026-01-01T00:00:00Z'} for r in old}
    return data,old,reviews


def test_hard_mining_deterministic_caps_labels_and_diagnostics(source, monkeypatch):
    import httpx
    monkeypatch.setattr(httpx.Client, '__init__', lambda *a,**k: pytest.fail('Mining must not use HTTP/AI'))
    data,old,reviews=source
    kwargs=dict(quotas=(4,4,2),cv_sample_size=6,cap=4,max_old=3,max_old_easy=1)
    first,selection,report=mine(data,old,reviews,**kwargs)
    second,_,_=mine(data,old,reviews,**kwargs)
    assert first==second
    assert report['total_pairs']==10
    assert len({r['pair_id'] for r in first})==10
    assert report['max_pairs_per_cv']<=4 and report['max_pairs_per_jd']<=4
    assert report['candidate_type_counts']['EASY_NEGATIVE_CANDIDATE']<=2
    assert report['hardness']['HARD_NEGATIVE_CANDIDATE']['median_lexical_overlap']>report['hardness']['EASY_NEGATIVE_CANDIDATE']['median_lexical_overlap']
    changed={pid:dict(r,human_label='1',human_reason='A different human reason.') for pid,r in reviews.items()}
    third,_,_=mine(data,old,changed,**kwargs)
    features=lambda rows:[{k:v for k,v in r.items() if k not in {'label','label_reason','human_label','human_reason'}} for r in rows]
    assert features(first)==features(third)
    for row in first:
        if row['pair_id'] in reviews:
            assert row['label']==reviews[row['pair_id']]['human_label']
            assert row['label_reason']==reviews[row['pair_id']]['human_reason']
            assert row['review_status']==reviews[row['pair_id']]['review_status']
            assert row['reviewed_at']==reviews[row['pair_id']]['reviewed_at']
        else:
            assert row['label']==row['label_reason']==''
            assert row['human_label']==row['human_reason']==''
            assert row['review_status']=='UNREVIEWED'
    assert sum(r['origin']=='OLD_SELECTED' and r['pair_type']=='EASY_NEGATIVE_CANDIDATE' for r in first)<=1


def test_archive_exact_versioning_and_pilot_workflow(source,tmp_path):
    data,old,reviews=source
    draft=tmp_path/'old.csv'; progress=tmp_path/'progress.csv'
    atomic_csv(draft,old,DRAFT_FIELDS); atomic_csv(progress,list(reviews.values()),PROGRESS_FIELDS)
    old_bytes=draft.read_bytes(); progress_bytes=progress.read_bytes()
    archive=archive_exact(draft,tmp_path/'archive','old.csv')
    assert archive.read_bytes()==old_bytes
    assert archive_exact(draft,tmp_path/'archive','old.csv')==archive
    modified=tmp_path/'other.csv'; modified.write_bytes(old_bytes+b'\n')
    version=archive_exact(modified,tmp_path/'archive','old.csv')
    assert version!=archive and archive.read_bytes()==old_bytes
    out=tmp_path/'out'; reports=tmp_path/'reports'
    main(['--data-dir',str(data),'--old-draft',str(draft),'--old-progress',str(progress),
          '--archive-dir',str(tmp_path/'archive2'),'--output-dir',str(out),'--reports-dir',str(reports),
          '--positive-count','4','--hard-count','4','--easy-count','2','--cv-sample-size','6'])
    assert draft.read_bytes()==old_bytes and progress.read_bytes()==progress_bytes
    pilot=list(csv.DictReader((out/'evaluation_pairs_pilot_reviewed.csv').open()))
    assert len(pilot)==3
    for r in pilot:
        assert r['human_reason']==reviews[r['pair_id']]['human_reason']
        assert r['reviewed_at']==reviews[r['pair_id']]['reviewed_at']
    store=LabelingStore(out/'evaluation_pairs_benchmark_seed.csv',data,out/'evaluation_labeling_progress_hard.csv',out/'labeled.csv')
    assert store.summary()['reviewed']>0
    seed_hash=hashlib.sha256((out/'evaluation_pairs_benchmark_seed.csv').read_bytes()).hexdigest()
    main(['--data-dir',str(data),'--old-draft',str(draft),'--old-progress',str(progress),
          '--archive-dir',str(tmp_path/'archive2'),'--output-dir',str(tmp_path/'out2'),'--reports-dir',str(tmp_path/'reports2'),
          '--positive-count','4','--hard-count','4','--easy-count','2','--cv-sample-size','6'])
    assert hashlib.sha256((tmp_path/'out2/evaluation_pairs_benchmark_seed.csv').read_bytes()).hexdigest()==seed_hash


def test_reviewed_duplicate_preserved_only_in_pilot(source,tmp_path):
    data,old,reviews=source
    with (data/'job_postings.csv').open(newline='',encoding='utf-8') as handle:
        jobs=list(csv.DictReader(handle))
    duplicate=dict(jobs[0],job_id='j9')
    atomic_csv(data/'job_postings.csv',jobs+[duplicate],list(jobs[0]))
    historical=dict(old[0],pair_id=make_pair_id('c0','j9'),job_id='j9')
    old.append(historical)
    reviews[historical['pair_id']]=dict(reviews[old[0]['pair_id']],pair_id=historical['pair_id'],job_id='j9')
    draft=tmp_path/'draft.csv'; progress=tmp_path/'progress.csv'; out=tmp_path/'out'
    atomic_csv(draft,old,DRAFT_FIELDS)
    atomic_csv(progress,list(reviews.values()),PROGRESS_FIELDS)
    main(['--data-dir',str(data),'--old-draft',str(draft),'--old-progress',str(progress),
          '--archive-dir',str(tmp_path/'archive'),'--output-dir',str(out),'--reports-dir',str(tmp_path/'reports'),
          '--positive-count','4','--hard-count','4','--easy-count','2','--cv-sample-size','6'])
    with (out/'evaluation_pairs_pilot_reviewed.csv').open(newline='',encoding='utf-8') as handle:
        pilot={r['pair_id']:r for r in csv.DictReader(handle)}
    with (out/'evaluation_pairs_benchmark_seed.csv').open(newline='',encoding='utf-8') as handle:
        seed=list(csv.DictReader(handle))
    with (tmp_path/'reports/old_pair_selection_report.csv').open(newline='',encoding='utf-8') as handle:
        selection={r['pair_id']:r for r in csv.DictReader(handle)}
    pid=historical['pair_id']
    assert len(pilot)==4 and pilot[pid]['human_reason']==reviews[pid]['human_reason']
    assert pid not in {r['pair_id'] for r in seed}
    assert selection[pid]['difficulty_bucket']=='NEAR_DUPLICATE'
    assert selection[pid]['selection_status']=='PILOT_ONLY'
    assert (tmp_path/'archive/evaluation_pairs_draft_old_400.csv').read_bytes()==draft.read_bytes()
