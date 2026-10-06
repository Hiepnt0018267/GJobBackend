"""Fresh dataset profile of the existing human labeling store; no scoring."""
import hashlib
import json
from pathlib import Path

from evaluation.common import EvaluationDataError, iter_csv
from evaluation.fresh_test_protocol import exclusion_files, validate_fresh_labels, validate_fresh_rows
from evaluation.labeling_store import LabelingStore


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FreshLabelingStore(LabelingStore):
    blind_labeling = True

    def __init__(self, draft, data_dir, progress, output, *, old_benchmark=None, min_rows=60, max_rows=80):
        self.old_benchmark = Path(old_benchmark) if old_benchmark else draft.with_name('evaluation_pairs_labeled.csv')
        self.min_rows, self.max_rows = min_rows, max_rows
        protected_names = {'evaluation_pairs_labeled.csv', 'evaluation_labeling_progress.csv',
                           'evaluation_labeling_progress_benchmark_seed.csv', 'evaluation_labeling_progress_hard.csv'}
        if any(path.name in protected_names for path in (progress, output)) or self.old_benchmark.resolve() in {progress.resolve(), output.resolve()}:
            raise EvaluationDataError('Fresh progress/output cannot overwrite historical benchmark/progress.')
        if progress.name != f'evaluation_labeling_progress_{draft.stem}.csv' or output.name != 'fresh_test_pairs_labeled.csv':
            raise EvaluationDataError('Fresh review requires its canonical dataset-scoped progress/output filenames.')
        rows = [r for _, r in iter_csv(draft)]
        validate_fresh_rows(rows, data_dir, self.old_benchmark, False, min_rows, max_rows)
        if any(r.get('label') or r.get('label_reason') or r.get('human_label') or r.get('human_reason') for r in rows):
            raise EvaluationDataError('Fresh seed must not contain prefilled human decisions; resume via its own progress.')
        self.draft_path, self.seed_sha = draft, sha(draft)
        self.old_sha = sha(self.old_benchmark)
        self.exclusion_hashes = {str(path.resolve()): sha(path) for path in exclusion_files(self.old_benchmark)}
        self.scope_path = progress.with_suffix('.dataset.json')
        expected = {'input_sha256': self.seed_sha, 'old_benchmark_sha256': self.old_sha,
                    'exclusion_file_hashes': self.exclusion_hashes, 'mode': 'fresh-blind-human-review'}
        if self.scope_path.exists():
            if json.loads(self.scope_path.read_text()) != expected:
                raise EvaluationDataError('Fresh progress dataset hash mismatch; refusing unrelated resume.')
        elif progress.exists():
            raise EvaluationDataError('Existing fresh progress has no dataset fingerprint; refusing blind import.')
        super().__init__(draft, data_dir, progress, output)
        if not self.scope_path.exists():
            self.scope_path.parent.mkdir(parents=True, exist_ok=True)
            with self.scope_path.open('x', encoding='utf-8') as handle:
                json.dump(expected, handle, indent=2); handle.write('\n')

    def persist(self):
        if sha(self.draft_path) != self.seed_sha or any(sha(path) != digest for path, digest in self.exclusion_hashes.items()):
            raise OSError('Fresh dataset changed during review; progress not saved.')
        super().persist()

    def pair(self, pid):
        data = super().pair(pid)
        # Keep legacy UI bindings functional, but reveal no sampling metadata.
        data['pair_type'] = ''
        data['cv'] = dict(data['cv'], category='')
        return data

    def validate_export(self, staging, final):
        if sha(self.draft_path) != self.seed_sha or any(sha(path) != digest for path, digest in self.exclusion_hashes.items()):
            raise EvaluationDataError('Fresh provenance changed; export blocked.')
        return validate_fresh_labels(staging, final, data_dir=self.data_dir,
            old_benchmark=self.old_benchmark, min_rows=self.min_rows, max_rows=self.max_rows)
