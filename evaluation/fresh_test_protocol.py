"""Fresh identity/source validation only; no matcher, model or score imports."""
from pathlib import Path

from evaluation.common import (EvaluationDataError, PAIR_TYPES, PAIR_ID_PATTERN, exact_text_hash,
    iter_csv, make_pair_id, near_duplicate_hash, normalize_identifier, resolve_dataset_files)
from evaluation.validate_labels import validate_labeled_file


def old_identities(path):
    # Read only identity columns into retained state. Labels/reasons are never features.
    cv_ids, job_ids, pair_ids = set(), set(), set()
    for _, row in iter_csv(Path(path), required_columns={'pair_id', 'cv_id', 'job_id'}):
        cv_ids.add(normalize_identifier(row['cv_id']))
        job_ids.add(normalize_identifier(row['job_id']))
        pair_ids.add(row['pair_id'])
    return cv_ids, job_ids, pair_ids


def exclusion_files(old_benchmark):
    primary = Path(old_benchmark)
    files = [primary]
    for name in ('evaluation_pairs_pilot_reviewed.csv', 'evaluation_pairs_draft.csv'):
        path = primary.with_name(name)
        if path.exists() and path.resolve() != primary.resolve():
            files.append(path)
    return files


def exclusion_identities(old_benchmark):
    result = (set(), set(), set())
    for path in exclusion_files(old_benchmark):
        identities = old_identities(path)
        for target, values in zip(result, identities):
            target.update(values)
    return result


def validate_fresh_rows(rows, data_dir, old_benchmark, require_labels=False, min_rows=60, max_rows=80):
    if not min_rows <= len(rows) <= max_rows:
        raise EvaluationDataError(f'Fresh dataset needs {min_rows}–{max_rows} pairs.')
    old_cvs, old_jobs, old_pairs = exclusion_identities(old_benchmark)
    seen_pairs, seen_cvs, seen_jobs = set(), set(), set()
    for row in rows:
        pid, cid, jid = row['pair_id'], row['cv_id'], row['job_id']
        if not PAIR_ID_PATTERN.fullmatch(pid) or pid != make_pair_id(cid, jid):
            raise EvaluationDataError('Invalid fresh pair ID.')
        if cid in old_cvs or jid in old_jobs or pid in old_pairs:
            raise EvaluationDataError('Fresh dataset reuses an old CV/JD/pair identity.')
        if pid in seen_pairs or cid in seen_cvs or jid in seen_jobs:
            raise EvaluationDataError('Duplicate/reused fresh CV/JD/pair identity.')
        seen_pairs.add(pid); seen_cvs.add(cid); seen_jobs.add(jid)
        if row['pair_type'] not in PAIR_TYPES or row.get('candidate_type', row['pair_type']) != row['pair_type']:
            raise EvaluationDataError('Invalid sampling category.')
        if require_labels and (row.get('label') not in {'0', '1'} or not row.get('label_reason', '').strip()):
            raise EvaluationDataError('Explicit human 0/1 label and non-empty reason required.')
        if not row.get('cv_source_row') or not row.get('job_source_row'):
            raise EvaluationDataError('Fresh source references required.')
    files = resolve_dataset_files(data_dir)
    found_cv, found_jobs, old_cv_texts, old_jd_texts = {}, {}, set(), set()
    for source_row, raw in iter_csv(files['Resume.csv']):
        cid = normalize_identifier(raw['ID'])
        if cid in old_cvs:
            old_cv_texts.add(exact_text_hash(raw['Resume_str']))
        if cid in seen_cvs:
            if cid in found_cv or not raw['Resume_str'].strip():
                raise EvaluationDataError('Ambiguous/empty fresh CV source.')
            found_cv[cid] = (source_row, exact_text_hash(raw['Resume_str']))
    for source_row, raw in iter_csv(files['job_postings.csv']):
        jid = normalize_identifier(raw['job_id'])
        if jid in old_jobs:
            old_jd_texts.add(near_duplicate_hash(raw['description']))
        if jid in seen_jobs:
            if jid in found_jobs or not raw['description'].strip() or not raw['title'].strip():
                raise EvaluationDataError('Ambiguous/empty fresh JD source.')
            found_jobs[jid] = (source_row, near_duplicate_hash(raw['description']))
    if set(found_cv) != seen_cvs or set(found_jobs) != seen_jobs:
        raise EvaluationDataError('Fresh source ID missing.')
    for row in rows:
        cv_ref, job_ref = found_cv[row['cv_id']], found_jobs[row['job_id']]
        if str(cv_ref[0]) != str(row['cv_source_row']) or str(job_ref[0]) != str(row['job_source_row']):
            raise EvaluationDataError('Fresh source row does not match source ID.')
        if cv_ref[1] in old_cv_texts or job_ref[1] in old_jd_texts:
            raise EvaluationDataError('Fresh text duplicates old benchmark content.')
    if len({v[1] for v in found_cv.values()}) != len(rows) or len({v[1] for v in found_jobs.values()}) != len(rows):
        raise EvaluationDataError('Duplicate fresh source content.')
    return {'rows': len(rows), 'unique_cvs': len(seen_cvs), 'unique_jobs': len(seen_jobs),
            'old_cv_overlap': 0, 'old_jd_overlap': 0, 'old_pair_overlap': 0}


def validate_fresh_labels(input_path, output_path, *, data_dir, old_benchmark, min_rows=60, max_rows=80):
    rows = [row for _, row in iter_csv(Path(input_path))]
    validate_fresh_rows(rows, data_dir, old_benchmark, True, min_rows, max_rows)
    return validate_labeled_file(input_path, output_path, data_dir=data_dir)
