"""Request-local, value-free extraction diagnostics; never a model input/output store."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

from pydantic import ValidationError
from pydantic_core import ErrorType
from typing import get_args


STAGES = (
    'document_parse_ms', 'prompt_build_ms', 'token_count_ms', 'preflight_ms',
    'provider_call_1_ms', 'json_parse_1_ms', 'schema_validate_1_ms',
    'source_date_resolution_ms',
    'correction_build_ms', 'provider_call_2_ms', 'json_parse_2_ms',
    'schema_validate_2_ms', 'persistence_ms', 'total_operation_ms',
)
CURRENT: ContextVar['ExtractionDiagnostics | None'] = ContextVar('cv_diagnostics', default=None)


def safe_validation_errors(error, schema):
    """Whitelist schema keys/error codes; exclude input, ctx, message and custom keys."""
    def keys(node):
        if isinstance(node, dict):
            found = set(node.get('properties', {}))
            for value in node.values():
                found.update(keys(value))
            return found
        if isinstance(node, list):
            return set().union(*(keys(value) for value in node))
        return set()
    allowed = keys(schema.model_json_schema())
    codes = set(get_args(ErrorType))
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, ValidationError):
            items = error.errors(include_input=False, include_url=False, include_context=False)
            return {'error_count': len(items), 'errors': [
                {'path': [part if (type(part) is int and part >= 0)
                          or (isinstance(part, str) and part in allowed) else 'unknown'
                          for part in item['loc']],
                 'type': item['type'] if item['type'] in codes else 'unknown'}
                for item in items[:50]], 'truncated': len(items) > 50}
        error = error.__cause__
    return {'error_count': None, 'errors': [], 'truncated': False}


class ExtractionDiagnostics:
    def __init__(self, deadline, clock=None):
        self.clock = clock or time.perf_counter
        self.started = self.clock()
        self.deadline = deadline
        self.timings = dict.fromkeys(STAGES)
        self.attempt = 1
        self.calls = []
        self.validation = {}
        self.date_resolution = {'status': 'not_run', 'items': []}
        self.active_stage = None
        self.last_stage = None
        self.terminal_stage = None
        self.correction = 'not_run'
        self.repair = {'attempted': False, 'patch_count': 0, 'validation_success': None}

    @contextmanager
    def stage(self, name):
        started = self.clock()
        prior = self.active_stage
        self.active_stage = name
        self.last_stage = name
        try:
            yield
        except BaseException:
            if self.terminal_stage is None:
                self.terminal_stage = name
            raise
        finally:
            elapsed = max(0.0, self.clock() - started) * 1000
            self.timings[name] = (self.timings.get(name) or 0.0) + elapsed
            self.active_stage = prior

    def begin_call(self, configured_timeout, num_predict):
        remaining = max(0.0, self.deadline - self.clock())
        row = {'attempt': self.attempt,
               'operation_elapsed_before_call_ms': max(0.0, self.clock() - self.started) * 1000,
               'remaining_operation_budget_before_call_ms': remaining * 1000,
               'configured_provider_timeout_ms': configured_timeout * 1000,
               'effective_provider_timeout_ms': min(configured_timeout, remaining) * 1000,
               'num_predict': num_predict}
        self.calls.append(row)
        return min(configured_timeout, remaining)

    def clear_handled_terminal(self, name):
        if self.terminal_stage == name:
            self.terminal_stage = None

    def snapshot(self):
        return {'timings': dict(self.timings), 'calls': list(self.calls),
                'validation': dict(self.validation), 'correction': self.correction,
                'date_resolution': dict(self.date_resolution),
                'repair': dict(self.repair),
                'terminal_stage': self.terminal_stage}


@contextmanager
def stage(name):
    diagnostics = CURRENT.get()
    if diagnostics is None:
        yield
    else:
        with diagnostics.stage(name):
            yield
