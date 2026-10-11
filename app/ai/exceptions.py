class DomainError(Exception):
    """Base domain exception."""

    pass


class AIProviderError(DomainError):
    """Lỗi chung từ AI provider."""

    pass


class AIConfigurationError(AIProviderError):
    """Lỗi cấu hình (thiếu key, sai provider, v.v.)."""

    pass


class AIAuthenticationError(AIProviderError):
    """Lỗi xác thực / API key không hợp lệ (401/403)."""

    pass


class AIProviderRequestError(AIProviderError):
    """The provider rejected a deterministic request or configuration."""

    pass


class AIRateLimitError(AIProviderError):
    """Hết quota hoặc vượt ngưỡng RPM/TPM (429)."""

    pass


class AITimeoutError(AIProviderError):
    """Yêu cầu gọi upstream AI bị quá thời gian chờ."""
    pass


class AIContextLimitError(AIProviderError):
    """The provider consumed too much of its configured input context."""

    pass


class AIResponseValidationError(AIProviderError):
    """The provider returned an empty, malformed, or schema-invalid response."""

    pass


class AIContextBudgetExceededError(AIContextLimitError):
    """Full rendered prompt plus output reservation cannot fit before generation."""


class AIOutputBudgetExceededError(AIProviderError):
    """Generation hit/exceeded the explicit output limit; never accept its JSON."""


class AITokenAccountingUnavailableError(AIProviderError):
    """Authoritative same-model/template counting could not be verified."""


class AIJSONParseError(AIResponseValidationError):
    """Complete provider envelope contains malformed JSON."""


class AISchemaValidationError(AIResponseValidationError):
    """Parsed JSON violates the requested domain schema."""


class AIPatchRepairError(AIResponseValidationError):
    """Fixed structural reason only; never contains payload values."""
