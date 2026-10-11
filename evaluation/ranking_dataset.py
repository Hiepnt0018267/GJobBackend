"""Offline per-job pool foundation. No matcher, predictions, provider or DB imports."""
import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from evaluation.common import EvaluationDataError, iter_csv, make_pair_id, stable_rank, near_duplicate_hash
from evaluation.hard_mining import FAMILIES, SPECIALTIES, family, specialty, terms
from evaluation.labeling_store import atomic_csv, locate_source

FIELDS = ['ranking_case_id', 'job_id', 'cv_id', 'pair_id', 'pool_position_seed',
          'source_status', 'candidate_source_ref', 'job_source_ref', 'job_title',
          'relevance_grade', 'relevance_reason']
RUBRIC = {
    '0': 'Không liên quan: thiếu năng lực cốt lõi hoặc khác biệt đáng kể về vai trò.',
    '1': 'Có tiềm năng: có năng lực liên quan/chuyển giao nhưng còn khoảng trống đáng kể.',
    '2': 'Liên quan mạnh: có bằng chứng đáng kể về nhiệm vụ, kỹ năng và yêu cầu cốt lõi.',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_id(job_id, source_hash, seed=42):
    return 'rank_job_' + stable_rank(seed, source_hash, job_id)[:20]


def sources(data_dir):
    paths = {name: locate_source(Path(data_dir), name) for name in ['Resume.csv', 'job_postings.csv']}
    cvs, jobs = {}, {}
    for ref, raw in iter_csv(paths['Resume.csv'], required_columns={'ID', 'Resume_str'}):
        cid = raw['ID'].strip()
        if not cid or cid in cvs:
            raise EvaluationDataError('Missing or duplicate CV identity in source.')
        cvs[cid] = {'ref': str(ref), 'text': raw['Resume_str']}
    for ref, raw in iter_csv(paths['job_postings.csv'], required_columns={'job_id', 'title', 'description'}):
        jid = raw['job_id'].strip()
        if not jid or jid in jobs:
            raise EvaluationDataError('Missing or duplicate job identity in source.')
        jobs[jid] = {'ref': str(ref), 'title': raw['title'],
                     'text': raw['description'] + '\n' + raw.get('skills_desc', '')}
    return cvs, jobs, {name: sha(path) for name, path in paths.items()}


def audit_pairs(paths):
    report = {}
    for path in paths:
        rows = [r for _, r in iter_csv(Path(path))]
        counts = Counter(r['job_id'] for r in rows)
        sizes = list(counts.values())
        report[str(path)] = {'pairs': len(rows), 'jobs': len(counts),
            'cvs': len({r['cv_id'] for r in rows}), 'mean': statistics.mean(sizes),
            'median': statistics.median(sizes), 'max': max(sizes),
            'buckets': {k: sum(lo <= n <= hi for n in sizes) for k, lo, hi in
                        [('1', 1, 1), ('2', 2, 2), ('3-4', 3, 4), ('5-9', 5, 9), ('10+', 10, 10**9)]},
            'at_least': {str(n): sum(v >= n for v in sizes) for n in [2, 3, 5, 10]}}
    return report


def generate(cvs, jobs, source_hash, old_rows=(), *, seed=42, job_count=10):
    """Content gates define sampling strata, never human relevance or matcher scores."""
    vocabulary = set().union(*(set(v.split()) for v in [*FAMILIES.values(), *SPECIALTIES.values()]))
    old_cvs = {r['cv_id'] for r in old_rows}
    old_jobs = {r['job_id'] for r in old_rows}
    cv_info, seen_cv = {}, set()
    for cid, cv in sorted(cvs.items()):
        digest = hashlib.sha256(' '.join(cv['text'].casefold().split()).encode()).hexdigest()
        if cid in old_cvs or len(cv['text'].strip()) < 200 or digest in seen_cv:
            continue
        seen_cv.add(digest)
        cv_info[cid] = (family(cv['text'], cv['text'][:500]), specialty(cv['text'][:3000]),
                        terms(cv['text']) & vocabulary)
    eligible = defaultdict(list)
    seen_jobs = set()
    for jid, job in sorted(jobs.items()):
        digest = near_duplicate_hash(job['text'])
        if jid in old_jobs or len(job['text'].strip()) < 200 or not job['title'].strip() or digest in seen_jobs:
            continue
        seen_jobs.add(digest)
        jf = family(job['text'][:1200], job['title'])
        if jf != 'unknown':
            eligible[jf].append(jid)
    selected, used = [], Counter()
    composition = {}
    # Round-robin families, hash within each family; no model-conditioned job choice.
    ordered = []
    families = sorted(eligible, key=lambda f: stable_rank(seed, 'family', f))
    for i in range(max((len(v) for v in eligible.values()), default=0)):
        for f in families:
            choices = sorted(eligible[f], key=lambda j: stable_rank(seed, 'job', j))
            if i < len(choices):
                ordered.append((f, choices[i]))
    for jf, jid in ordered:
        job = jobs[jid]
        js = specialty(job['title'] + ' ' + job['text'][:1500])
        jt = terms(job['text']) & vocabulary
        buckets = defaultdict(list)
        for cid, (cf, cs, ct) in cv_info.items():
            if used[cid] >= 2:
                continue
            shared = len(ct & jt)
            mismatch = cs != 'unknown' and js != 'unknown' and cs != js
            if cf == jf and shared >= 5 and not mismatch:
                bucket = 'role_aligned'
            elif shared >= 3 and mismatch:
                bucket = 'specialization_challenge'
            elif shared >= 3:
                bucket = 'related_transferable'
            elif cf != jf and cf != 'unknown' and shared <= 1:
                bucket = 'cross_domain_sanity'
            else:
                continue
            buckets[bucket].append(cid)
        quotas = {'role_aligned': 3, 'related_transferable': 3,
                  'specialization_challenge': 3, 'cross_domain_sanity': 1}
        if any(len(buckets[k]) < n for k, n in quotas.items()):
            continue
        chosen = [cid for k, n in quotas.items() for cid in
                  sorted(buckets[k], key=lambda c: stable_rank(seed, jid, k, c))[:n]]
        case = case_id(jid, source_hash, seed)
        composition[case] = {'role_family': jf, 'sampling_counts_not_relevance': quotas}
        for position, cid in enumerate(sorted(chosen, key=lambda c: stable_rank(seed, 'review', jid, c)), 1):
            selected.append(dict(zip(FIELDS, [case, jid, cid, make_pair_id(cid, jid), str(position),
                'NEW', cvs[cid]['ref'], job['ref'], job['title'], '', ''])))
            used[cid] += 1
        if len(composition) == job_count:
            break
    if len(composition) < job_count:
        raise EvaluationDataError(f'Only {len(composition)} content-qualified pools; target {job_count}. No relaxed fallback.')
    return selected, {'composition': composition, 'max_cv_reuse': max(used.values()),
                      'role_families': len({v['role_family'] for v in composition.values()}),
                      'sampling_is_not_relevance': True}


def validate(rows, cvs, jobs, *, labeled=False, minimum_pool=6):
    if not rows:
        raise EvaluationDataError('Empty ranking dataset.')
    groups, pairs, by_job = defaultdict(list), set(), {}
    for row in rows:
        jid, cid, case = row['job_id'], row['cv_id'], row['ranking_case_id']
        if not case or jid not in jobs or cid not in cvs:
            raise EvaluationDataError('Missing case or source identity.')
        if row['pair_id'] != make_pair_id(cid, jid) or row['pair_id'] in pairs:
            raise EvaluationDataError('Invalid/duplicate pair.')
        pairs.add(row['pair_id'])
        if jid in by_job and by_job[jid] != case:
            raise EvaluationDataError('Job assigned inconsistent ranking cases.')
        by_job[jid] = case
        if any(r['job_id'] != jid or r['cv_id'] == cid for r in groups[case]):
            raise EvaluationDataError('Inconsistent case or duplicate candidate.')
        if row['candidate_source_ref'] != cvs[cid]['ref'] or row['job_source_ref'] != jobs[jid]['ref']:
            raise EvaluationDataError('Source row reference mismatch.')
        if not cvs[cid]['text'].strip() or not jobs[jid]['text'].strip() or row['job_title'] != jobs[jid]['title']:
            raise EvaluationDataError('Empty source content or mismatched job title.')
        if row['source_status'] not in {'NEW', 'REUSED_REVIEWED'}:
            raise EvaluationDataError('Invalid source provenance.')
        grade, reason = row['relevance_grade'], row['relevance_reason']
        if (labeled or grade or reason) and (grade not in RUBRIC or not reason.strip()):
            raise EvaluationDataError('Explicit grade 0/1/2 and non-empty human reason required.')
        groups[case].append(row)
    flags = {}
    for case, pool in groups.items():
        if len(pool) < minimum_pool:
            raise EvaluationDataError(f'Pool {case} too small: {len(pool)}; minimum {minimum_pool}.')
        positions = [r['pool_position_seed'] for r in pool]
        if set(positions) != {str(i) for i in range(1, len(pool) + 1)}:
            raise EvaluationDataError('Pool neutral positions must be unique and contiguous.')
        counts = Counter(r['relevance_grade'] for r in pool)
        warnings = []
        if labeled:
            if len(counts) == 1: warnings.append('ALL_SAME_GRADE')
            if not counts['1'] and not counts['2']: warnings.append('NO_RELEVANT_CANDIDATE')
            if not counts['0']: warnings.append('NO_NEGATIVE')
        flags[case] = {'size': len(pool), 'grade_counts': {g: counts[g] for g in RUBRIC}, 'flags': warnings}
    return {'rows': len(rows), 'cases': len(groups), 'jobs': len(by_job),
            'unique_cvs': len({r['cv_id'] for r in rows}), 'pools': flags}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--output', default='evaluation/data/derived/ranking_pairs_seed.csv')
    parser.add_argument('--manifest', default='evaluation/results/ranking-dataset/seed_manifest.json')
    args = parser.parse_args(argv)
    out, manifest = Path(args.output), Path(args.manifest)
    if out.exists() or manifest.exists():
        parser.error('Refuse to overwrite ranking seed/provenance.')
    old_paths = [Path('evaluation/data/derived') / n for n in
                 ['evaluation_pairs_labeled.csv', 'fresh_test_pairs_labeled.csv',
                  'evaluation_pairs_draft.csv', 'evaluation_pairs_pilot_reviewed.csv']]
    old_rows = [r for p in old_paths for _, r in iter_csv(p)]
    cvs, jobs, hashes = sources(args.data_dir)
    rows, info = generate(cvs, jobs, hashes['job_postings.csv'], old_rows)
    validation = validate(rows, cvs, jobs)
    atomic_csv(out, rows, FIELDS)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open('x', encoding='utf-8') as handle:
        json.dump({'task': '14C.1', 'phase': 'A', 'seed': 42, 'frozen_ground_truth': False,
                   'seed_sha256': sha(out), 'source_hashes': hashes, 'old_input_hashes': {str(p): sha(p) for p in old_paths},
                   'existing_pair_audit': audit_pairs(old_paths[:2]), 'generation': info, 'validation': validation,
                   'generator_sha256': sha(__file__), 'relevance_rubric': RUBRIC}, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'rows': len(rows), 'jobs': validation['jobs'], 'unique_cvs': validation['unique_cvs'],
                      'seed_sha256': sha(out), 'role_families': info['role_families']}))


if __name__ == '__main__':
    main()
