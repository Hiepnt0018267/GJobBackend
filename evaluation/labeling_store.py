"""Local labeling state. AI suggestions and human ground truth are separate."""
from __future__ import annotations

import csv
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from evaluation.common import EvaluationDataError, iter_csv, make_pair_id, normalize_identifier
from evaluation.validate_labels import FINAL_FIELDS, REQUIRED_DRAFT_FIELDS, validate_labeled_file

PROGRESS_FIELDS = ['pair_id', 'cv_id', 'job_id', 'ai_suggested_label', 'ai_reason',
                   'ai_model', 'ai_generated_at', 'human_label', 'human_reason',
                   'review_status', 'reviewed_at']


def atomic_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.labeling-', suffix='.csv', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def locate_source(root: Path, filename: str) -> Path:
    matches = list(root.rglob(filename))
    if len(matches) != 1:
        raise EvaluationDataError(f'Expected exactly one {filename} under {root}; found {len(matches)}.')
    return matches[0]


class LabelingStore:
    def __init__(self, draft: Path, data_dir: Path, progress: Path, output: Path):
        self.data_dir, self.progress_path, self.output_path = data_dir, progress, output
        self.lock = threading.RLock()
        paths = [draft.resolve(), progress.resolve(), output.resolve()]
        if len(set(paths)) != 3:
            raise EvaluationDataError('Draft, progress and output must be different files.')
        self.rows = [row for _, row in iter_csv(draft, required_columns=REQUIRED_DRAFT_FIELDS)]
        if not self.rows:
            raise EvaluationDataError('Draft has no pairs.')
        seen = set()
        for row in self.rows:
            pair = (row['cv_id'], row['job_id'])
            if row['pair_id'] != make_pair_id(*pair) or pair in seen:
                raise EvaluationDataError('Draft has an invalid pair_id or duplicate pair.')
            seen.add(pair)
        self.by_id = {row['pair_id']: row for row in self.rows}
        needed_cv = {r['cv_id'] for r in self.rows}
        needed_jd = {r['job_id'] for r in self.rows}
        self.cvs, self.jobs = {}, {}
        for _, row in iter_csv(locate_source(data_dir, 'Resume.csv'), required_columns={'ID', 'Resume_str', 'Category'}):
            key = normalize_identifier(row['ID'])
            if key in needed_cv:
                if key in self.cvs:
                    raise EvaluationDataError(f'Ambiguous duplicate CV ID: {key}')
                self.cvs[key] = {'id': key, 'category': row['Category'], 'text': row['Resume_str']}
        for _, row in iter_csv(locate_source(data_dir, 'job_postings.csv'), required_columns={'job_id', 'title', 'description'}):
            key = normalize_identifier(row['job_id'])
            if key in needed_jd:
                if key in self.jobs:
                    raise EvaluationDataError(f'Ambiguous duplicate job ID: {key}')
                self.jobs[key] = {'id': key, 'title': row['title'], 'text': row['description']}
        if needed_cv - self.cvs.keys() or needed_jd - self.jobs.keys():
            raise EvaluationDataError('Draft references CV/JD IDs missing from the source dataset.')
        if any(not r['text'].strip() for r in [*self.cvs.values(), *self.jobs.values()]):
            raise EvaluationDataError('A referenced CV/JD has empty source text.')
        # Seed decisions are authoritative initial state, even without a progress file.
        self.progress = {}
        for row in self.rows:
            label = row.get('human_label') or row.get('label', '')
            reason = row.get('human_reason') or row.get('label_reason', '')
            if not label and not reason:
                continue
            if label not in {'0', '1'} or not reason.strip() or row.get('review_status', 'REVIEWED') != 'REVIEWED':
                raise EvaluationDataError('Input contains an incomplete embedded human decision.')
            self.progress[row['pair_id']] = dict.fromkeys(PROGRESS_FIELDS, '') | {
                'pair_id': row['pair_id'], 'cv_id': row['cv_id'], 'job_id': row['job_id'],
                'human_label': label, 'human_reason': reason, 'review_status': 'REVIEWED',
                'reviewed_at': row.get('reviewed_at', '')}
        if progress.exists():
            loaded = set()
            for _, record in iter_csv(progress, required_columns=PROGRESS_FIELDS):
                pid = record['pair_id']
                if pid not in self.by_id or pid in loaded:
                    raise EvaluationDataError('Progress belongs to a different input dataset or contains duplicate pair IDs. Use a dataset-scoped --progress file.')
                loaded.add(pid)
                draft_row = self.by_id[pid]
                if (record['cv_id'], record['job_id']) != (draft_row['cv_id'], draft_row['job_id']):
                    raise EvaluationDataError('Progress source IDs do not match the draft.')
                if record['review_status'] == 'REVIEWED' and (record['human_label'] not in {'0', '1'} or not record['human_reason'].strip()):
                    raise EvaluationDataError('Progress contains an incomplete reviewed decision.')
                embedded = self.progress.get(pid)
                if embedded and record['review_status'] != 'REVIEWED':
                    # An unreviewed cache row must not erase a preserved seed decision.
                    record.update({key: embedded[key] for key in ('human_label', 'human_reason', 'review_status', 'reviewed_at')})
                self.progress[pid] = record

    def state(self, pid: str) -> dict:
        row = self.by_id[pid]
        return dict(self.progress.get(pid, {
            **{k: '' for k in PROGRESS_FIELDS}, 'pair_id': pid, 'cv_id': row['cv_id'],
            'job_id': row['job_id'], 'review_status': 'UNREVIEWED',
        }))

    def persist(self) -> None:
        atomic_csv(self.progress_path, [self.state(r['pair_id']) for r in self.rows], PROGRESS_FIELDS)

    def suggestion(self, pid: str, label: int, reason: str, model: str) -> None:
        if type(label) is not int or label not in {0, 1} or not reason.strip():
            raise EvaluationDataError('Invalid AI suggestion.')
        with self.lock:
            record = self.state(pid)
            record.update(ai_suggested_label=str(label), ai_reason=reason.strip(), ai_model=model,
                          ai_generated_at=datetime.now(timezone.utc).isoformat())
            old = self.progress.get(pid)
            self.progress[pid] = record
            try:
                self.persist()
            except OSError:
                if old is None:
                    self.progress.pop(pid)
                else:
                    self.progress[pid] = old
                raise

    def review(self, pid: str, label: str, reason: str) -> None:
        if label not in {'0', '1'} or not reason.strip():
            raise EvaluationDataError('Choose 0 or 1 and enter a non-empty human reason.')
        with self.lock:
            record = self.state(pid)
            record.update(human_label=label, human_reason=reason.strip(), review_status='REVIEWED',
                          reviewed_at=datetime.now(timezone.utc).isoformat())
            old = self.progress.get(pid)
            self.progress[pid] = record
            try:
                self.persist()
            except OSError:
                if old is None:
                    self.progress.pop(pid)
                else:
                    self.progress[pid] = old
                raise

    def summary(self) -> dict:
        with self.lock:
            entries = [self.state(r['pair_id']) for r in self.rows]
            reviewed = sum(e['review_status'] == 'REVIEWED' for e in entries)
            return {'total': len(entries), 'reviewed': reviewed, 'remaining': len(entries) - reviewed,
                    'pairs': entries, 'resume_index': next((i for i, e in enumerate(entries) if e['review_status'] != 'REVIEWED'), 0)}

    def pair(self, pid: str) -> dict:
        with self.lock:
            row = self.by_id[pid]
            return {'pair_id': pid, 'pair_type': row['pair_type'], 'cv': self.cvs[row['cv_id']],
                    'job': self.jobs[row['job_id']], 'progress': self.state(pid)}

    def validate_export(self, staging: Path, final: Path) -> dict:
        return validate_labeled_file(staging, final, data_dir=self.data_dir)

    def export(self) -> dict:
        with self.lock:
            if self.summary()['remaining']:
                raise EvaluationDataError('Export blocked: every pair needs a human label and reason.')
            rows = []
            for source in self.rows:
                state = self.state(source['pair_id'])
                fields = REQUIRED_DRAFT_FIELDS | set(FINAL_FIELDS)
                row = {key: source.get(key, '') for key in sorted(fields)}
                row.update(label=state['human_label'], label_reason=state['human_reason'])
                # Source IDs retain linkage; source-aware validator checks full text.
                row['cv_text_preview'] = row['job_text_preview'] = ''
                rows.append(row)
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.labeling-export-', dir=self.output_path.parent) as directory:
                staging = Path(directory) / 'labeled.csv'
                atomic_csv(staging, rows, list(rows[0]))
                result = self.validate_export(staging, Path(directory) / 'final.csv')
                os.replace(staging, self.output_path)
            return {**result, 'validation': 'PASS', 'output': str(self.output_path)}
