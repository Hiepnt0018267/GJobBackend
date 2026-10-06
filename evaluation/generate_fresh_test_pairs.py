"""Phase A sampling only: no evaluation scores, old outcomes, thresholds or model calls."""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from evaluation.common import (EvaluationConfig, EvaluationDataError, REQUIRED_COLUMNS,
    exact_text_hash, iter_csv, make_pair_id, near_duplicate_hash, normalize_identifier,
    normalize_whitespace, resolve_dataset_files, stable_rank)
from evaluation.fresh_test_protocol import exclusion_files, exclusion_identities, old_identities, validate_fresh_rows
from evaluation.generate_pairs import DRAFT_FIELDS, _balanced_sample, _load_jobs, _load_resumes
from evaluation.hard_mining import HardMiner

GROUPS = {'INFORMATIVE_POSITIVE_CANDIDATE': 'POSITIVE_CANDIDATE',
          'INFORMATIVE_HARD_NEGATIVE_CANDIDATE': 'HARD_NEGATIVE_CANDIDATE',
          'EASY_SANITY_CANDIDATE': 'EASY_NEGATIVE_CANDIDATE'}
FIELDS = DRAFT_FIELDS + ['candidate_type']


def raw_audit(path, kind):
    counts = Counter()
    excluded = []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED_COLUMNS[path.name] <= set(reader.fieldnames or ()):
            raise EvaluationDataError('Source schema missing required fields.')
        for source_row, row in enumerate(reader, start=2):
            counts['total'] += 1
            identity = row.get('ID' if kind == 'cv' else 'job_id')
            text = row.get('Resume_str' if kind == 'cv' else 'description')
            if None in row or not identity or not row.get('Category' if kind == 'cv' else 'title'):
                counts['malformed'] += 1
                excluded.append(source_row)
            elif not text or not text.strip():
                counts['blank'] += 1
                excluded.append(source_row)
            elif len(normalize_whitespace(text)) < (200 if kind == 'cv' else 100):
                counts['short'] += 1
                excluded.append(source_row)
    return dict(counts), set(excluded)


def mine_fresh(data_dir, old_benchmark, seed=42, quotas=(28, 32, 10), sample_size=400):
    files = resolve_dataset_files(data_dir)
    primary_cvs, primary_jobs, _ = old_identities(old_benchmark)
    old_cvs, old_jobs, old_pairs = exclusion_identities(old_benchmark)
    config = EvaluationConfig(seed=seed, cv_sample_size=100000, job_sample_size=100000)
    cvs, cv_stats = _load_resumes(files['Resume.csv'], config)
    jobs, job_stats = _load_jobs(files, config)
    cv_audit, bad_cvs = raw_audit(files['Resume.csv'], 'cv')
    jd_audit, bad_jobs = raw_audit(files['job_postings.csv'], 'job')
    cvs = [cv for cv in cvs if cv.source_row not in bad_cvs]
    jobs = [job for job in jobs if job.source_row not in bad_jobs]
    old_cv_texts, old_jd_texts = set(), set()
    for _, row in iter_csv(files['Resume.csv']):
        if normalize_identifier(row['ID']) in old_cvs:
            old_cv_texts.add(exact_text_hash(row['Resume_str']))
    for _, row in iter_csv(files['job_postings.csv']):
        if normalize_identifier(row['job_id']) in old_jobs:
            old_jd_texts.add(near_duplicate_hash(row['description']))
    fresh_cvs = [cv for cv in cvs if cv.cv_id not in old_cvs and exact_text_hash(cv.text) not in old_cv_texts]
    fresh_jobs, seen_descriptions = [], set()
    for job in sorted(jobs, key=lambda j: j.job_id):
        digest = near_duplicate_hash(job.description)
        if job.job_id in old_jobs or digest in old_jd_texts or digest in seen_descriptions:
            continue
        seen_descriptions.add(digest); fresh_jobs.append(job)
    sampled = _balanced_sample(fresh_cvs, lambda cv: cv.category, lambda cv: cv.cv_id, sample_size, seed)
    pool_audit = {'cv_raw': cv_audit, 'jd_raw': jd_audit,
        'cv_loader': cv_stats, 'jd_loader': job_stats, 'old_cv_ids': len(old_cvs), 'old_jd_ids': len(old_jobs),
        'primary_220_cv_ids': len(primary_cvs), 'primary_220_jd_ids': len(primary_jobs),
        'additional_historical_cv_ids': len(old_cvs - primary_cvs), 'additional_historical_jd_ids': len(old_jobs - primary_jobs),
        'old_cv_eligible_excluded': sum(cv.cv_id in old_cvs for cv in cvs),
        'old_jd_eligible_excluded': sum(job.job_id in old_jobs for job in jobs),
        'fresh_cvs': len(fresh_cvs), 'fresh_jobs': len(fresh_jobs), 'sampled_cvs': len(sampled),
        'eligible_cv_after_quality': len(cvs), 'eligible_jd_after_quality': len(jobs),
        'cv_extra_content_excluded': len(cvs) - len(fresh_cvs) - sum(cv.cv_id in old_cvs for cv in cvs),
        'jd_extra_duplicate_content_excluded': len(jobs) - len(fresh_jobs) - sum(job.job_id in old_jobs for job in jobs)}
    print(json.dumps({'fresh_pool_audit': pool_audit}), flush=True)
    if len(fresh_cvs) < sum(quotas) or len(fresh_jobs) < sum(quotas):
        raise EvaluationDataError('Not enough independent source identities for target.')
    miner = HardMiner(sampled, fresh_jobs, seed)
    by_job = {job.job_id: job for job in fresh_jobs}
    pools = {}
    for cv in sampled:
        candidates = []
        for jid in miner.retrieve(cv.cv_id):
            evidence = miner.evidence(cv.cv_id, jid)
            bucket = miner.classify(evidence)
            if bucket in GROUPS:
                # Rank by seeded hash within content-qualified pools; never a matcher score.
                candidates.append((bucket, stable_rank(seed, 'fresh-pair', cv.cv_id, jid), jid))
        pools[cv.cv_id] = sorted(candidates)
    remaining = dict(zip(GROUPS, quotas)); used_cvs, used_jobs, used_pairs = set(), set(), set()
    rows, categories, domains = [], Counter(), Counter()
    category_cap = max(4, math.ceil(sum(quotas) / max(1, len({cv.category for cv in sampled}))) + 1)
    progress = True
    while any(remaining.values()) and progress:
        progress = False
        # Hard pool first to reserve confusing cases before filling plausible/easy pools.
        for bucket in ('INFORMATIVE_HARD_NEGATIVE_CANDIDATE', 'INFORMATIVE_POSITIVE_CANDIDATE', 'EASY_SANITY_CANDIDATE'):
            if not remaining[bucket]:
                continue
            for cv in sorted(sampled, key=lambda c: (categories[c.category], stable_rank(seed, 'fresh-cv', c.cv_id))):
                if cv.cv_id in used_cvs or categories[cv.category] >= category_cap:
                    continue
                jid = next((jid for candidate, _, jid in pools[cv.cv_id] if candidate == bucket and jid not in used_jobs), None)
                if jid is None:
                    continue
                job = by_job[jid]; pid = make_pair_id(cv.cv_id, jid)
                if pid in old_pairs or pid in used_pairs:
                    continue
                record = dict.fromkeys(FIELDS, '')
                record.update(pair_id=pid, cv_id=cv.cv_id, job_id=jid, pair_type=GROUPS[bucket],
                    candidate_type=GROUPS[bucket], cv_category=cv.category, job_title=job.title,
                    cv_source_row=cv.source_row, job_source_row=job.source_row)
                rows.append(record); used_cvs.add(cv.cv_id); used_jobs.add(jid); used_pairs.add(pid)
                categories[cv.category] += 1; domains[miner.job_family[jid]] += 1
                remaining[bucket] -= 1; progress = True
                if not remaining[bucket]:
                    break
    if any(remaining.values()):
        raise EvaluationDataError(f'Independent useful pools cannot fill frozen quotas: {remaining}; no arbitrary fallback.')
    rows.sort(key=lambda r: stable_rank(seed, 'fresh-output', r['pair_id']))
    report = {'seed': seed, 'target': sum(quotas), 'rows': len(rows), 'pool_audit': pool_audit,
        'candidate_counts': dict(Counter(r['pair_type'] for r in rows)), 'unique_cvs': len(used_cvs), 'unique_jobs': len(used_jobs),
        'category_distribution': dict(categories), 'job_domain_distribution': dict(domains),
        'old_cv_overlap': 0, 'old_jd_overlap': 0, 'old_pair_overlap': 0,
        'sampling': 'Existing professional-family/mismatch/title/lexical evidence gates; seeded selection, no evaluation/model scoring.',
        'sampling_metadata_not_ground_truth': True, 'all_labels_blank': True,
        'raw_previews_omitted': True, 'model_scores_computed': False}
    return rows, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--old-benchmark', default='evaluation/data/derived/evaluation_pairs_labeled.csv')
    parser.add_argument('--output', default='evaluation/data/derived/fresh_test_pairs_seed.csv')
    parser.add_argument('--report', default='evaluation/reports/fresh_test_generation_report.json')
    args = parser.parse_args(argv)
    output, report_path = Path(args.output), Path(args.report)
    if output.exists() or report_path.exists():
        parser.error('Fresh artifacts already exist; refusing regeneration/overwrite.')
    if hashlib.sha256(Path(args.old_benchmark).read_bytes()).hexdigest() != '28f371400b637045155ca12543869052998be29b3f8a3b575b7e46313851fad8':
        parser.error('Original frozen 220-pair benchmark hash differs; stop before generation.')
    rows, report = mine_fresh(Path(args.data_dir), Path(args.old_benchmark))
    report['validation'] = validate_fresh_rows(rows, Path(args.data_dir), Path(args.old_benchmark))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, FIELDS); writer.writeheader(); writer.writerows(rows)
    report.update(seed_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        old_benchmark_sha256=hashlib.sha256(Path(args.old_benchmark).read_bytes()).hexdigest(),
        exclusion_file_hashes={str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in exclusion_files(Path(args.old_benchmark))},
        source_hashes={name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in resolve_dataset_files(Path(args.data_dir)).items()},
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        sampling_code_sha256=hashlib.sha256(Path(__file__).with_name('hard_mining.py').read_bytes()).hexdigest())
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, sort_keys=True); handle.write('\n')
    print(json.dumps({key: report[key] for key in ('rows', 'candidate_counts', 'unique_cvs', 'unique_jobs', 'seed_sha256')}), flush=True)


if __name__ == '__main__':
    main()
