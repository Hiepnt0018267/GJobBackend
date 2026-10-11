import asyncio
import json
import time
import logging
import sys
from pydantic import ValidationError

from app.ai import AIProvider, AIProviderError, AIResponseValidationError, create_ai_provider
from app.ai.exceptions import (
    AIContextLimitError,
    AIRateLimitError,
    AIProviderRequestError,
    AITokenAccountingUnavailableError,
    AITimeoutError, AIOutputBudgetExceededError, AIContextBudgetExceededError,
    AIJSONParseError, AISchemaValidationError,
    AIPatchRepairError,
)
from app.ai.cv_extraction_prompt import (
    CV_EXTRACTION_SYSTEM_INSTRUCTION,
    build_cv_extraction_prompt,
)
from app.core.config import settings
from app.ai.extraction_diagnostics import CURRENT, ExtractionDiagnostics, stage, safe_validation_errors
from app.models.cv import CV
from app.schemas.cv_extraction import StructuredCVExtractionResult
from app.schemas.cv_extraction_wire import (
    CVExtractionProviderResponse,
    validate_reconciled_provider_response,
)
from app.services.cv_text_extraction_service import (
    CVTextExtractionService,
    UploadedCVTextSource,
)
from app.services.cv_patch_repair_service import repair_once
from app.services.cv_source_date_reconciliation import (
    SourceDateResolutionError,
    reconcile_source_grounded_dates,
)


class CVStructuredExtractionError(RuntimeError):
    """Base error for safe, non-persistent structured CV extraction."""


class CVStructuredExtractionInputError(CVStructuredExtractionError):
    pass


class CVExtractionValidationError(CVStructuredExtractionError):
    pass


class CVExtractionJSONError(CVExtractionValidationError):
    pass


class CVExtractionSchemaError(CVExtractionValidationError):
    pass


class CVExtractionCorrectionError(CVExtractionValidationError):
    pass


class CVExtractionDeadlineError(CVStructuredExtractionError):
    """The total extraction operation deadline was exceeded before a valid result."""


class CVAIProviderUnavailableError(CVStructuredExtractionError):
    pass


class CVAIProviderTimeoutError(CVAIProviderUnavailableError):
    pass


class CVAIOutputBudgetError(CVStructuredExtractionError):
    pass


class CVAITokenAccountingError(CVAIProviderUnavailableError):
    pass


class CVAIRateLimitError(CVStructuredExtractionError):
    """Gemini remained rate limited after the bounded retry policy."""

    pass


class CVAIContextLimitError(CVStructuredExtractionError):
    """The selected provider exhausted the configured context window."""

    pass


class CVAIContextBudgetError(CVAIContextLimitError):
    pass


class CVAIProviderRequestError(CVStructuredExtractionError):
    """The provider rejected GJob's deterministic request configuration."""

    pass


class CVStructuredExtractionService:
    def __init__(
        self,
        provider: AIProvider | None = None,
        text_extraction_service: CVTextExtractionService | None = None,
        correction_only: bool = False,
        max_schema_retries: int = 1,
        repair_provider: AIProvider | None = None,
    ) -> None:
        if correction_only:
            raise ValueError('Full-source correction-only mode is disabled; repair requires a retained parsed payload.')
        self.provider = provider if provider is not None else create_ai_provider()
        self.generation_attempts = 0
        self.last_diagnostics = None
        self.schema_retries = 0
        self.correction_only = correction_only
        self.repair_provider = repair_provider
        if max_schema_retries not in (0, 1):
            raise ValueError("Schema retries must be zero or one.")
        self.max_schema_retries = max_schema_retries
        self.text_extraction_service = (
            text_extraction_service
            if text_extraction_service is not None
            else CVTextExtractionService()
        )

    async def extract_from_text(self, cv_text: str, *, deadline: float | None = None) -> StructuredCVExtractionResult:
        if CURRENT.get() is None:
            deadline = deadline if deadline is not None else time.perf_counter() + settings.cv_extraction_total_timeout_seconds
            return await self._diagnosed_extract(cv_text=cv_text, deadline=deadline)
        return await self._extract_from_text(cv_text, deadline=deadline)

    async def _diagnosed_extract(self, *, cv_text=None, cv=None, deadline):
        diagnostics = ExtractionDiagnostics(deadline, clock=time.perf_counter)
        self.last_diagnostics = diagnostics
        token = CURRENT.set(diagnostics)
        try:
            if cv is not None:
                async with asyncio.timeout(max(0, deadline - time.perf_counter())):
                    with stage('document_parse_ms'):
                        document = await asyncio.to_thread(self.text_extraction_service.extract_uploaded_cv, cv)
                    return await self._extract_from_text(document.text, deadline=deadline)
            return await self._extract_from_text(cv_text, deadline=deadline)
        except TimeoutError as exc:
            raise CVExtractionDeadlineError('The complete extraction operation exceeded its time budget.') from exc
        finally:
            diagnostics.timings['total_operation_ms'] = max(0, time.perf_counter() - diagnostics.started) * 1000
            # Failed summaries must remain visible with Uvicorn's normal WARNING
            # application-log level; successful summaries are INFO only.
            log = logging.getLogger(__name__).warning if sys.exc_info()[0] is not None else logging.getLogger(__name__).info
            log('CV extraction diagnostics=%s', json.dumps(diagnostics.snapshot()))
            CURRENT.reset(token)

    async def _extract_from_text(self, cv_text: str, *, deadline: float | None = None) -> StructuredCVExtractionResult:
        normalized_text = cv_text.strip()
        if not normalized_text:
            raise CVStructuredExtractionInputError("CV text must not be empty.")
        if len(normalized_text) > settings.CV_EXTRACTED_TEXT_MAX_CHARACTERS:
            raise CVStructuredExtractionInputError(
                "CV text exceeds the configured extraction limit."
            )

        deadline = deadline if deadline is not None else time.perf_counter() + settings.cv_extraction_total_timeout_seconds
        total_deadline = deadline - time.perf_counter()
        if total_deadline <= 0:
            raise CVExtractionDeadlineError("The extraction operation has no time remaining.")
        correction_min = settings.cv_extraction_correction_min_seconds
        started_at = time.perf_counter()

        try:
            async with asyncio.timeout(total_deadline):
                try:
                    correction_started = self.correction_only
                    # Primary request/success path unchanged. Invalid parseable
                    # schema results enter one patch helper, never iteration2.
                    attempts = 1
                    for attempt in range(attempts):
                        diagnostics = CURRENT.get()
                        diagnostics.attempt = attempt + 1
                        diagnostics.terminal_stage = None
                        with stage('correction_build_ms' if attempt > 0 or self.correction_only else 'prompt_build_ms'):
                            correction = ''
                        # Guard correction pass: only start if sufficient time budget remains.
                        if (attempt > 0 or self.correction_only) and deadline - time.perf_counter() < correction_min:
                            diagnostics.correction = 'blocked_insufficient_budget'
                            diagnostics.terminal_stage = 'correction_admission'
                            raise CVExtractionDeadlineError(
                                "Insufficient time remaining to attempt extraction correction."
                            )
                        self.generation_attempts += 1
                        if attempt > 0:
                            correction_started = True
                            self.schema_retries += 1
                        if correction_started:
                            diagnostics.correction = 'started'
                        with stage('correction_build_ms' if correction_started else 'prompt_build_ms'):
                            prompt = build_cv_extraction_prompt(normalized_text) + correction
                        logging.getLogger(__name__).info("CV extraction attempt=%s remaining_seconds=%.3f", attempt + 1, deadline - time.perf_counter())
                        try:
                            payload = None
                            payload = await self.provider.generate_structured(
                                prompt=prompt,
                                response_schema=CVExtractionProviderResponse,
                                system_instruction=CV_EXTRACTION_SYSTEM_INSTRUCTION,
                                temperature=0.0,
                            )
                            if hasattr(payload, "model_dump"):
                                payload = payload.model_dump(mode="json", exclude_unset=True)
                            try:
                                with stage('source_date_resolution_ms'):
                                    resolution = reconcile_source_grounded_dates(normalized_text, payload)
                                diagnostics.date_resolution = {
                                    'status': 'resolved' if resolution.audit else 'not_needed',
                                    'items': list(resolution.audit),
                                    'certificate_date_omitted_count': resolution.diagnostics.get('certificate_date_omitted_count', 0),
                                    'issue_date_omitted_count': resolution.diagnostics.get('issue_date_omitted_count', 0),
                                    'expiration_date_omitted_count': resolution.diagnostics.get('expiration_date_omitted_count', 0),
                                }
                                payload = resolution.payload
                            except SourceDateResolutionError as resolution_error:
                                diagnostics.date_resolution = {
                                    'status': 'failed',
                                    'reason': resolution_error.code,
                                    'detail_reason': resolution_error.detail_code,
                                    'path': [resolution_error.entity_type, resolution_error.entity_index],
                                    'matcher': resolution_error.diagnostics,
                                    'items': [],
                                    'certificate_date_omitted_count': 0,
                                    'issue_date_omitted_count': 0,
                                    'expiration_date_omitted_count': 0,
                                }
                                logging.getLogger(__name__).warning(
                                    'CV source-date resolution failed reason=%s detail=%s path=%s[%s] matcher=%s',
                                    resolution_error.code,
                                    resolution_error.detail_code,
                                    resolution_error.entity_type,
                                    resolution_error.entity_index,
                                    json.dumps(resolution_error.diagnostics, sort_keys=True),
                                )
                                raise CVExtractionCorrectionError(
                                    'CV dates could not be reconciled safely from source evidence.'
                                ) from resolution_error
                            with stage(f'schema_validate_{attempt + 1}_ms'):
                                validated = validate_reconciled_provider_response(
                                    payload,
                                    validation_context=resolution.validation_context,
                                )
                            if time.perf_counter() >= deadline:
                                raise CVExtractionDeadlineError("Validation exceeded the extraction deadline.")
                            return validated
                        except (AIResponseValidationError, ValidationError) as error:
                            summary = safe_validation_errors(error, CVExtractionProviderResponse)
                            diagnostics.validation[str(attempt + 1)] = summary
                            logging.getLogger(__name__).warning('CV schema diagnostics attempt=%s correction=%s summary=%s', attempt + 1, correction_started, json.dumps(summary))
                            if isinstance(error, AISchemaValidationError):
                                payload = getattr(error, '_invalid_payload', None)
                                error._invalid_payload = None
                            cause = error
                            while cause is not None and not isinstance(cause, ValidationError):
                                cause = cause.__cause__
                            if self.max_schema_retries and payload is not None and isinstance(cause, ValidationError):
                                try:
                                    return await repair_once(payload, cause, diagnostics, deadline, self.repair_provider)
                                except AIPatchRepairError as repair_error:
                                    raise CVExtractionCorrectionError('AI returned data that does not match the CV schema; bounded patch repair failed safely.') from repair_error
                                except TimeoutError as repair_error:
                                    if diagnostics.correction == 'blocked_insufficient_budget':
                                        raise CVExtractionDeadlineError('Insufficient time remaining for bounded patch repair.') from repair_error
                                    raise
                                finally:
                                    if diagnostics.repair['attempted']:
                                        self.schema_retries += 1
                                        self.generation_attempts += 1
                            raise
                except (AIResponseValidationError, ValidationError) as exc:
                    failure_type = CVExtractionCorrectionError if correction_started else (
                        CVExtractionJSONError if isinstance(exc, AIJSONParseError) else CVExtractionSchemaError if isinstance(exc, (AISchemaValidationError, ValidationError)) else CVExtractionValidationError)
                    logging.getLogger(__name__).warning("CV extraction invalid result type=%s correction=%s", type(exc).__name__, correction_started)
                    raise failure_type(
                        "AI returned data that does not match the CV schema."
                    ) from exc
                except AIProviderRequestError as exc:
                    raise CVAIProviderRequestError(
                        "The AI provider rejected the structured extraction request."
                    ) from exc
                except AIRateLimitError as exc:
                    raise CVAIRateLimitError(
                        "Structured CV extraction is temporarily rate limited."
                    ) from exc
                except AIContextLimitError as exc:
                    failure_type = CVAIContextBudgetError if isinstance(exc, AIContextBudgetExceededError) else CVAIContextLimitError
                    raise failure_type(
                        "CV content exceeds the safe AI context limit."
                    ) from exc
                except AIOutputBudgetExceededError as exc:
                    raise CVAIOutputBudgetError("Extraction exhausted the output budget.") from exc
                except AITokenAccountingUnavailableError as exc:
                    raise CVAITokenAccountingError("Extraction runtime safety/accounting is unavailable.") from exc
                except AITimeoutError as exc:
                    raise CVAIProviderTimeoutError("The extraction provider timed out.") from exc
                except (CVExtractionDeadlineError, CVStructuredExtractionError):
                    raise
                except AIProviderError as exc:
                    raise CVAIProviderUnavailableError(
                        "Structured CV extraction is temporarily unavailable."
                    ) from exc
        except TimeoutError as exc:
            raise CVExtractionDeadlineError(
                "The extraction operation exceeded its total time budget."
            ) from exc

    async def extract_uploaded_cv(
        self, cv: CV | UploadedCVTextSource
    ) -> StructuredCVExtractionResult:
        deadline = time.perf_counter() + settings.cv_extraction_total_timeout_seconds
        return await self._diagnosed_extract(cv=cv, deadline=deadline)
