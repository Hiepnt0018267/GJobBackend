"""Human-only graded review, bound to seed and source hashes; no score/AI imports."""
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from evaluation.common import EvaluationDataError, iter_csv
from evaluation.labeling_store import atomic_csv
from evaluation.ranking_dataset import FIELDS, RUBRIC, sha, sources, validate

PROGRESS_FIELDS = ['seed_sha256', 'source_identity', 'pair_id', 'relevance_grade',
                   'relevance_reason', 'review_status', 'reviewed_at']


class RankingLabelingStore:
    is_ranking = True

    def __init__(self, draft, data_dir, progress, output, manifest):
        self.draft, self.progress_path, self.output_path = map(Path, [draft, progress, output])
        self.manifest_path = Path(manifest)
        self.data_dir = Path(data_dir)
        if len({p.resolve() for p in [self.draft, self.progress_path, self.output_path, self.manifest_path]}) != 4:
            raise EvaluationDataError('Seed, progress, output and manifest must be different.')
        if self.progress_path.name != 'ranking_labeling_progress.csv' or self.output_path.name != 'ranking_pairs_labeled.csv':
            raise EvaluationDataError('Use ranking-only progress/output filenames; old labeling data must not be reused.')
        self.rows = [r for _, r in iter_csv(self.draft, required_columns=FIELDS)]
        if any(r['relevance_grade'] or r['relevance_reason'] for r in self.rows):
            raise EvaluationDataError('Ranking seed must start blank; graded decisions belong only in scoped progress.')
        self.cvs, self.jobs, hashes = sources(data_dir)
        validate(self.rows, self.cvs, self.jobs)
        manifest_data = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.seed_hash = sha(self.draft)
        if manifest_data['seed_sha256'] != self.seed_hash or manifest_data['source_hashes'] != hashes:
            raise EvaluationDataError('Seed/source identity differs from generation manifest.')
        self.source_identity = json.dumps(hashes, sort_keys=True)
        self.by_id = {r['pair_id']: r for r in self.rows}
        self.progress, self.lock = {}, threading.RLock()
        self.progress_digest = sha(self.progress_path) if self.progress_path.exists() else None
        if self.progress_path.exists():
            for _, record in iter_csv(self.progress_path, required_columns=PROGRESS_FIELDS):
                pid = record['pair_id']
                if pid not in self.by_id or pid in self.progress:
                    raise EvaluationDataError('Progress contains unrelated/duplicate pairs.')
                if record['seed_sha256'] != self.seed_hash or record['source_identity'] != self.source_identity:
                    raise EvaluationDataError('Progress belongs to another seed/source identity.')
                if record['review_status'] == 'REVIEWED':
                    self._decision(record['relevance_grade'], record['relevance_reason'])
                    if not record['reviewed_at']: raise EvaluationDataError('Reviewed timestamp missing.')
                elif record['review_status'] != 'UNREVIEWED' or record['relevance_grade'] or record['relevance_reason']:
                    raise EvaluationDataError('Invalid unreviewed record.')
                self.progress[pid] = record
        self.summary_path = self.manifest_path.with_name('dataset_summary.json')
        self.frozen = self.output_path.exists() or self.summary_path.exists()
        if self.frozen:
            if not self.output_path.exists() or not self.summary_path.exists():
                raise EvaluationDataError('Incomplete export/freeze; inspect artifacts before continuing.')
            summary = json.loads(self.summary_path.read_text())
            if summary['sha256'] != sha(self.output_path) or summary['seed_sha256'] != self.seed_hash:
                raise EvaluationDataError('Frozen ranking output changed.')
        # Never create or alter real progress during startup.

    @staticmethod
    def _decision(grade, reason):
        if grade not in RUBRIC or not isinstance(reason, str) or not reason.strip():
            raise EvaluationDataError('Choose grade 0/1/2 and enter a non-empty human reason.')

    def state(self, pid):
        return dict(self.progress.get(pid, dict(zip(PROGRESS_FIELDS,
            [self.seed_hash, self.source_identity, pid, '', '', 'UNREVIEWED', '']))))

    def _assert_current(self):
        if self.frozen or self.output_path.exists() or self.summary_path.exists():
            raise EvaluationDataError('Dataset exported/frozen or export interrupted; inspect artifacts, no mutation allowed.')
        if sha(self.draft) != self.seed_hash:
            raise EvaluationDataError('Seed changed during review; restart with correct provenance.')
        digest = sha(self.progress_path) if self.progress_path.exists() else None
        if digest != self.progress_digest:
            raise EvaluationDataError('Another session changed progress; restart to avoid losing human decisions.')

    @contextmanager
    def _mutation(self):
        # Exclusive local file guards all cooperating processes, not only threads.
        # A leftover lock after process termination blocks safely; never guess-remove it.
        lock_path = self.progress_path.with_suffix('.lock')
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            try:
                handle = lock_path.open('x', encoding='utf-8')
            except FileExistsError as exc:
                raise EvaluationDataError('Review write lock is busy; retry or inspect an interrupted session.') from exc
            try:
                self._assert_current()
                yield
            finally:
                handle.close()
                lock_path.unlink()

    def review(self, pid, label, reason):
        self._decision(label, reason)
        with self._mutation():
            if self.frozen: raise EvaluationDataError('Dataset frozen; corrections require a new version.')
            if pid not in self.by_id: raise EvaluationDataError('Unknown pair.')
            record = self.state(pid)
            record.update(relevance_grade=label, relevance_reason=reason.strip(), review_status='REVIEWED',
                          reviewed_at=datetime.now(timezone.utc).isoformat())
            updated = dict(self.progress, **{pid: record})
            atomic_csv(self.progress_path, [updated.get(r['pair_id'], self.state(r['pair_id'])) for r in self.rows], PROGRESS_FIELDS)
            self.progress = updated
            self.progress_digest = sha(self.progress_path)

    def summary(self):
        with self.lock:
            entries = [{'pair_id': r['pair_id'], 'ranking_case_id': r['ranking_case_id'],
                        'job_title': r['job_title'], 'review_status': self.state(r['pair_id'])['review_status']}
                       for r in self.rows]
            reviewed = sum(r['review_status'] == 'REVIEWED' for r in entries)
            return {'total': len(entries), 'reviewed': reviewed, 'remaining': len(entries)-reviewed,
                    'pairs': entries, 'frozen': self.frozen, 'rubric': RUBRIC,
                    'resume_index': next((i for i, r in enumerate(entries) if r['review_status'] != 'REVIEWED'), 0)}

    def pair(self, pid):
        with self.lock:
            row = self.by_id[pid]
            record = self.state(pid)
            return {'pair_id': pid, 'ranking_case_id': row['ranking_case_id'],
                    'cv': {'text': self.cvs[row['cv_id']]['text']},
                    'job': {'title': self.jobs[row['job_id']]['title'], 'text': self.jobs[row['job_id']]['text']},
                    'progress': {k: record[k] for k in ['relevance_grade', 'relevance_reason', 'review_status']}}

    def export(self):
        with self._mutation():
            from evaluation.labeling_store import locate_source
            current_sources = {name: sha(locate_source(Path(self.data_dir), name)) for name in
                               ['Resume.csv', 'job_postings.csv']}
            if json.dumps(current_sources, sort_keys=True) != self.source_identity:
                raise EvaluationDataError('Source files changed during review; export blocked.')
            if self.frozen: raise EvaluationDataError('Already exported/frozen; no overwrite.')
            if any(self.state(r['pair_id'])['review_status'] != 'REVIEWED' for r in self.rows):
                raise EvaluationDataError('Review every candidate before Validate & Export.')
            rows = [dict(r, relevance_grade=self.state(r['pair_id'])['relevance_grade'],
                         relevance_reason=self.state(r['pair_id'])['relevance_reason']) for r in self.rows]
            result = validate(rows, self.cvs, self.jobs, labeled=True)
            atomic_csv(self.output_path, rows, FIELDS)
            sizes = [p['size'] for p in result['pools'].values()]
            import statistics
            summary = dict(result, task='14C.1', seed=42, ranking_cases=result['cases'], pairs=result['rows'],
                unique_jobs=result['jobs'], pool_size={'min': min(sizes), 'mean': statistics.mean(sizes),
                    'median': statistics.median(sizes), 'max': max(sizes)},
                grade_distribution={g: sum(r['relevance_grade'] == g for r in rows) for g in RUBRIC},
                sha256=sha(self.output_path), seed_sha256=self.seed_hash, frozen=True,
                binary_relevance_policy='Deferred to Task14C.2', ranking_metrics_computed=False)
            # Exclusive marker: interrupted export is visibly incomplete on restart.
            with self.summary_path.open('x', encoding='utf-8') as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
            self.frozen = True
            return dict(result, output=str(self.output_path), sha256=summary['sha256'])
