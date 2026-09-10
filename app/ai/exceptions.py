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

class AIRateLimitError(AIProviderError):
    """Hết quota hoặc vượt ngưỡng RPM/TPM (429)."""
    pass

class AITimeoutError(AIProviderError):
    """Yêu cầu gọi upstream AI bị quá thời gian chờ."""
    pass