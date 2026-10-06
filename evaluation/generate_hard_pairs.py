"""Archive the legacy pilot and mine a harder benchmark without using human answers."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from evaluation.common import (EvaluationConfig, EvaluationDataError, iter_csv, make_pair_id,
                               near_duplicate_hash, resolve_dataset_files, stable_rank)
from evaluation.generate_pairs import DRAFT_FIELDS, JobRecord, _load_jobs, _load_resumes
from evaluation.hard_mining import HardMiner
from evaluation.labeling_store import PROGRESS_FIELDS, atomic_csv

BUCKET_TYPES = {'INFORMATIVE_POSITIVE_CANDIDATE': 'POSITIVE_CANDIDATE',
                'INFORMATIVE_HARD_NEGATIVE_CANDIDATE': 'HARD_NEGATIVE_CANDIDATE',
                'EASY_SANITY_CANDIDATE': 'EASY_NEGATIVE_CANDIDATE'}
SEED_FIELDS = DRAFT_FIELDS + ['candidate_type', 'origin', 'difficulty_bucket', 'lexical_overlap',
                             'title_overlap', 'domain_overlap', 'cv_family', 'job_family',
                             'mismatch_cues', 'human_label', 'human_reason', 'review_status', 'reviewed_at']


def archive_exact(source: Path, directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        target = directory / f'{Path(name).stem}_{digest[:16]}.csv'
    if target.exists():
        if target.read_bytes() != source.read_bytes():
            raise EvaluationDataError('Archive collision; refusing overwrite.')
    else:
        # Exclusive creation prevents overwriting a historical archive.
        with source.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst)
    return target


def reviewed_records(progress: Path | None, old_rows: list[dict]) -> dict[str, dict]:
    by_id = {r['pair_id']: r for r in old_rows}
    result = {}
    if progress and progress.exists():
        seen = set()
        for _, record in iter_csv(progress, required_columns=PROGRESS_FIELDS):
            pid = record['pair_id']
            if pid in seen or pid not in by_id or (record['cv_id'], record['job_id']) != (by_id[pid]['cv_id'], by_id[pid]['job_id']):
                raise EvaluationDataError('Invalid or duplicate progress source reference.')
            seen.add(pid)
            if record['review_status'] == 'REVIEWED':
                if record['human_label'] not in {'0', '1'} or not record['human_reason'].strip():
                    raise EvaluationDataError('Incomplete human decision in progress; refusing to lose it.')
                result[pid] = record
    # Also preserve explicitly human-labeled legacy input if no progress entry exists.
    for row in old_rows:
        if row.get('label') in {'0', '1'} and row.get('label_reason', '').strip() and row['pair_id'] not in result:
            result[row['pair_id']] = dict.fromkeys(PROGRESS_FIELDS, '') | {
                'pair_id': row['pair_id'], 'cv_id': row['cv_id'], 'job_id': row['job_id'],
                'human_label': row['label'], 'human_reason': row['label_reason'],
                'review_status': 'REVIEWED', 'reviewed_at': row.get('reviewed_at', '')}
    return result


def diagnostics(rows: list[dict]) -> dict:
    groups = {}
    for pair_type in BUCKET_TYPES.values():
        subset = [r for r in rows if r['pair_type'] == pair_type]
        groups[pair_type] = {
            'count': len(subset),
            'median_lexical_overlap': statistics.median(float(r['lexical_overlap']) for r in subset) if subset else None,
            'median_title_overlap': statistics.median(float(r['title_overlap']) for r in subset) if subset else None,
            'same_domain_rate': round(sum(int(r['domain_overlap']) for r in subset) / len(subset), 6) if subset else None,
        }
    return groups


def mine(data_dir: Path, old_rows: list[dict], reviews: dict[str, dict], seed=42,
         quotas: tuple[int, int, int] = (90, 100, 30), cv_sample_size=300, cap=4,
         max_old=60, max_old_easy=10) -> tuple[list[dict], list[dict], dict]:
    files = resolve_dataset_files(data_dir)
    config = EvaluationConfig(seed=seed, cv_sample_size=10000, job_sample_size=100000)
    all_cvs, _ = _load_resumes(files['Resume.csv'], config)
    # Preserve coverage from the original CV sample, then add a stratified sample.
    wanted = {r['cv_id'] for r in old_rows}
    sample_config = EvaluationConfig(seed=seed, cv_sample_size=cv_sample_size)
    sampled, _ = _load_resumes(files['Resume.csv'], sample_config)
    cvs = [r for r in all_cvs if r.cv_id in wanted | {c.cv_id for c in sampled}]
    jobs, _ = _load_jobs(files, config)
    # Restore legacy duplicate jobs for diagnostics only; they cannot enter mining.
    old_jids = {r['job_id'] for r in old_rows}
    by_job = {j.job_id: j for j in jobs}
    for source_row, r in iter_csv(files['job_postings.csv']):
        if r['job_id'] in old_jids and r['job_id'] not in by_job:
            by_job[r['job_id']] = JobRecord(r['job_id'], r['title'], r['description'],
                r.get('skills_desc', ''), r.get('formatted_experience_level', ''), source_row, (), ())
    canonical = set()
    seen_hashes = set()
    for job in sorted(by_job.values(), key=lambda j: j.job_id):
        digest = near_duplicate_hash(job.description)
        if digest not in seen_hashes:
            canonical.add(job.job_id)
            seen_hashes.add(digest)
    miner = HardMiner(cvs, list(by_job.values()), seed)
    cv_by_id = {cv.cv_id: cv for cv in cvs}
    old_info = []
    old_by_pair = {r['pair_id']: r for r in old_rows}
    for old in old_rows:
        if old['pair_id'] != make_pair_id(old['cv_id'], old['job_id']):
            raise EvaluationDataError('Invalid legacy pair ID.')
        if old['cv_id'] not in cv_by_id or old['job_id'] not in by_job:
            raise EvaluationDataError('Legacy pair source missing from eligible source data.')
        e = miner.evidence(old['cv_id'], old['job_id'])
        bucket = miner.classify(e) if old['job_id'] in canonical else 'NEAR_DUPLICATE'
        old_info.append({'pair_id': old['pair_id'], 'cv_id': old['cv_id'], 'job_id': old['job_id'],
                         'was_reviewed': old['pair_id'] in reviews, 'candidate_type': old['pair_type'],
                         'difficulty_bucket': bucket, **asdict(e),
                         'near_duplicate_flag': old['job_id'] not in canonical})
    quota = dict(zip(BUCKET_TYPES.values(), quotas))
    rows, used = [], set()
    cv_usage, jd_usage, category_usage = Counter(), Counter(), Counter()
    per_category = max(8, round(sum(quotas) / max(1, len({c.category for c in cvs}))) + 6)

    def accept(cid, jid, bucket, origin):
        pid = make_pair_id(cid, jid)
        pair_type = BUCKET_TYPES.get(bucket)
        cv, job = cv_by_id[cid], by_job[jid]
        if origin == 'OLD_SELECTED' and (sum(r['origin']=='OLD_SELECTED' for r in rows) >= max_old or
                (bucket == 'EASY_SANITY_CANDIDATE' and sum(r['origin']=='OLD_SELECTED' and r['pair_type']=='EASY_NEGATIVE_CANDIDATE' for r in rows) >= max_old_easy)):
            return False
        if not pair_type or quota[pair_type] <= 0 or pid in used or cv_usage[cid] >= cap or jd_usage[jid] >= cap or category_usage[cv.category] >= per_category:
            return False
        e = miner.evidence(cid, jid)
        record = {field: '' for field in SEED_FIELDS}
        record.update(pair_id=pid, cv_id=cid, job_id=jid, pair_type=pair_type, candidate_type=pair_type,
                      cv_category=cv.category, job_title=job.title, job_industry='|'.join(job.industry_ids),
                      sampling_score=e.sampling_score, cv_source_row=cv.source_row, job_source_row=job.source_row,
                      cv_skills_hint='|'.join(e.shared_terms), job_skills_hint='|'.join(job.skill_codes),
                      origin=origin, difficulty_bucket=bucket, lexical_overlap=e.lexical_overlap,
                      title_overlap=e.title_overlap, domain_overlap=e.domain_overlap,
                      cv_family=e.cv_family, job_family=e.job_family, mismatch_cues='|'.join(e.mismatch_cues),
                      review_status='UNREVIEWED')
        if pid in reviews:
            review = reviews[pid]
            record.update(label=review['human_label'], label_reason=review['human_reason'],
                          human_label=review['human_label'], human_reason=review['human_reason'],
                          review_status=review['review_status'], reviewed_at=review['reviewed_at'])
        rows.append(record)
        used.add(pid)
        quota[pair_type] -= 1
        cv_usage[cid] += 1; jd_usage[jid] += 1; category_usage[cv.category] += 1
        return True

    old_ranked = sorted(old_info, key=lambda r: (not r['was_reviewed'], r['difficulty_bucket'] == 'EASY_SANITY_CANDIDATE',
                         -r['sampling_score'], stable_rank(seed, r['pair_id'])))
    easy_old = 0
    for info in old_ranked:
        if len(rows) >= max_old:
            break
        if info['difficulty_bucket'] == 'EASY_SANITY_CANDIDATE' and easy_old >= max_old_easy:
            continue
        if accept(info['cv_id'], info['job_id'], info['difficulty_bucket'], 'OLD_SELECTED'):
            easy_old += info['difficulty_bucket'] == 'EASY_SANITY_CANDIDATE'
    # Candidate pools and sorting depend only on source content, never human labels/reasons.
    pools = {}
    for cv in cvs:
        candidates = []
        for jid in miner.retrieve(cv.cv_id):
            if jid not in canonical:
                continue
            e = miner.evidence(cv.cv_id, jid)
            bucket = miner.classify(e)
            if bucket in BUCKET_TYPES:
                priority = -e.sampling_score if bucket == 'INFORMATIVE_POSITIVE_CANDIDATE' else abs(e.lexical_overlap - .23)
                candidates.append((bucket, priority, stable_rank(seed, cv.cv_id, jid), jid))
        pools[cv.cv_id] = sorted(candidates)
    order = sorted(cvs, key=lambda cv: (stable_rank(seed, 'category', cv.category), stable_rank(seed, cv.cv_id)))
    made_progress = True
    while any(quota.values()) and made_progress:
        made_progress = False
        for bucket in BUCKET_TYPES:
            for cv in sorted(order, key=lambda c: (category_usage[c.category], cv_usage[c.cv_id], stable_rank(seed, c.cv_id))):
                for cb, _, _, jid in pools[cv.cv_id]:
                    if cb == bucket and accept(cv.cv_id, jid, bucket, 'OLD_SELECTED' if make_pair_id(cv.cv_id,jid) in old_by_pair else 'NEW_MINED'):
                        made_progress = True
                        break
    for info in old_info:
        if info['pair_id'] in used:
            status, reason = 'INCLUDED_MAIN_BENCHMARK', 'Content-based usefulness gate passed; within quota and reuse caps.'
        elif info['was_reviewed']:
            status, reason = 'PILOT_ONLY', f"Preserved human work; content bucket {info['difficulty_bucket']} or diversity/reuse budget excluded it."
        elif info['near_duplicate_flag']:
            status, reason = 'ARCHIVE_NEAR_DUPLICATE', 'Repeated normalized JD description.'
        elif info['difficulty_bucket'] == 'TOO_TRIVIAL':
            status, reason = 'ARCHIVE_TRIVIAL', 'Insufficient profession-specific evidence for informative mining.'
        else:
            status, reason = 'ARCHIVE_REDUNDANT', 'Not selected within category, reuse or candidate-type quota.'
        info.update(selection_status=status, selection_reason=reason)
        info['mismatch_cues'] = '|'.join(info['mismatch_cues'])
        info['shared_terms'] = '|'.join(info['shared_terms'])
    rows.sort(key=lambda r: stable_rank(seed, 'output', r['pair_id']))
    hardness = diagnostics(rows)
    hard_median = hardness['HARD_NEGATIVE_CANDIDATE']['median_lexical_overlap']
    easy_median = hardness['EASY_NEGATIVE_CANDIDATE']['median_lexical_overlap']
    if hard_median is None or easy_median is None or hard_median <= easy_median * 1.5:
        raise EvaluationDataError('Hardness diagnostics failed; refusing to publish a trivial benchmark.')
    report = {'seed': seed, 'target': sum(quotas), 'total_pairs': len(rows), 'quota_shortfall': quota,
              'candidate_type_counts': dict(Counter(r['pair_type'] for r in rows)),
              'old_total': len(old_rows), 'old_reviewed': len(reviews), 'old_unreviewed': len(old_rows) - len(reviews),
              'old_selected': sum(r['origin'] == 'OLD_SELECTED' for r in rows),
              'new_generated': sum(r['origin'] == 'NEW_MINED' for r in rows),
              'new_candidate_type_counts': dict(Counter(r['pair_type'] for r in rows if r['origin'] == 'NEW_MINED')),
              'final_reviewed': sum(r['review_status'] == 'REVIEWED' for r in rows),
              'final_unreviewed': sum(r['review_status'] != 'REVIEWED' for r in rows),
              'selection_status_counts': dict(Counter(r['selection_status'] for r in old_info)),
              'unique_cvs': len(cv_usage), 'unique_jobs': len(jd_usage),
              'max_pairs_per_cv': max(cv_usage.values(), default=0), 'max_pairs_per_jd': max(jd_usage.values(), default=0),
              'category_distribution': dict(category_usage), 'domain_distribution': dict(Counter(r['job_family'] for r in rows)),
              'title_family_coverage': dict(Counter(miner.job_specialty[r['job_id']] for r in rows)),
              'industry_coverage': dict(Counter(code for r in rows for code in r['job_industry'].split('|') if code)),
              'duplicate_pairs': len(rows) - len(used), 'near_duplicate_jds_excluded': len(by_job) - len(canonical),
              'hardness': hardness, 'old_hardness': diagnostics([dict(r, pair_type=r['candidate_type']) for r in old_info]),
              'limitations': ['Candidate types are not ground truth.', 'Role/specialization vocabularies are lexical cues, not formal taxonomies.',
                             'Seniority from CV introduction can be missing or ambiguous.', 'No skill_abr semantics are invented.',
                             'TOO_TRIVIAL/ARCHIVE_TRIVIAL means insufficient mining evidence, not a human judgment of irrelevance.',
                             'Hardness diagnostics verify lexical separation only, not benchmark accuracy.'],
              'examples': {kind: [{k:r[k] for k in ('pair_id','cv_id','job_id','job_title','cv_family','job_family','mismatch_cues','lexical_overlap','title_overlap')}
                                 for r in rows if r['pair_type']==kind][:count]
                           for kind,count in zip(BUCKET_TYPES.values(), (5,10,5))}}
    return rows, old_info, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--old-draft', default='evaluation/data/derived/evaluation_pairs_draft.csv')
    parser.add_argument('--old-progress', default='evaluation/data/derived/evaluation_labeling_progress.csv')
    parser.add_argument('--output-dir', default='evaluation/data/derived')
    parser.add_argument('--archive-dir', default='evaluation/data/archive')
    parser.add_argument('--reports-dir', default='evaluation/reports')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--positive-count', type=int, default=90)
    parser.add_argument('--hard-count', type=int, default=100)
    parser.add_argument('--easy-count', type=int, default=30)
    parser.add_argument('--cv-sample-size', type=int, default=300)
    args = parser.parse_args(argv)
    draft, progress = Path(args.old_draft), Path(args.old_progress)
    out, reports = Path(args.output_dir), Path(args.reports_dir)
    protected = [out / name for name in ('evaluation_pairs_pilot_reviewed.csv','evaluation_pairs_benchmark_seed.csv','evaluation_pairs_hard_draft.csv','evaluation_labeling_progress_hard.csv')]
    if any(p.exists() for p in protected):
        parser.error('New artifacts already exist. Use a fresh --output-dir; never overwrite reviewed work.')
    archives = [archive_exact(draft, Path(args.archive_dir), 'evaluation_pairs_draft_old_400.csv')]
    if progress.exists():
        archives.append(archive_exact(progress, Path(args.archive_dir), 'evaluation_labeling_progress_old.csv'))
    old = [r for _,r in iter_csv(archives[0])]
    reviews = reviewed_records(archives[1] if len(archives)>1 else None, old)
    pilot = []
    for row in old:
        if row['pair_id'] in reviews:
            r = reviews[row['pair_id']]
            pilot.append(dict(row, **r, label=r['human_label'], label_reason=r['human_reason']))
    if pilot:
        atomic_csv(out/'evaluation_pairs_pilot_reviewed.csv', pilot, list(pilot[0]))
    rows, selection, report = mine(Path(args.data_dir), old, reviews, args.seed,
        quotas=(args.positive_count, args.hard_count, args.easy_count), cv_sample_size=args.cv_sample_size)
    atomic_csv(out/'evaluation_pairs_benchmark_seed.csv', rows, SEED_FIELDS)
    atomic_csv(out/'evaluation_pairs_hard_draft.csv', [r for r in rows if r['origin']=='NEW_MINED'], SEED_FIELDS)
    progress_rows = []
    for row in rows:
        r = dict.fromkeys(PROGRESS_FIELDS, '')
        r.update({k:row.get(k,'') for k in ('pair_id','cv_id','job_id','human_label','human_reason','review_status','reviewed_at')})
        progress_rows.append(r)
    atomic_csv(out/'evaluation_labeling_progress_hard.csv', progress_rows, PROGRESS_FIELDS)
    reports.mkdir(parents=True, exist_ok=True)
    atomic_csv(reports/'old_pair_selection_report.csv', selection, list(selection[0]))
    report['archive_files'] = [str(p) for p in archives]
    report['sha256'] = hashlib.sha256((out/'evaluation_pairs_benchmark_seed.csv').read_bytes()).hexdigest()
    (reports/'hard_pair_distribution.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Hard pair generation report', '', '## Root cause of the old set', '',
             'The old sampler narrowed jobs to 140 before retrieval, treated moderate generic overlap as hard, allowed arbitrary fallback jobs, and grouped titles by sorted first token.', '',
             '## Summary', '', '```json', json.dumps({k:v for k,v in report.items() if k!='examples'}, ensure_ascii=False, indent=2), '```', '',
             '## Candidate examples (not ground truth)', '']
    for kind, examples in report['examples'].items():
        lines += [f'### {kind}', '', '| CV ID / family | JD / family | Lexical | Mismatch cues |', '|---|---|---:|---|']
        for r in examples:
            lines.append(f"| {r['cv_id']} / {r['cv_family']} | {r['job_id']}: {r['job_title'].replace('|','/')} / {r['job_family']} | {r['lexical_overlap']} | {r['mismatch_cues']} |")
        lines.append('')
    (reports/'hard_pair_generation_report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('total_pairs','old_reviewed','old_selected','new_generated','final_reviewed','candidate_type_counts','hardness','sha256')}, indent=2))


if __name__ == '__main__':
    main()
