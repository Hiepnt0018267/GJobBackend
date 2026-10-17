# pyrefly: ignore [missing-import]
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    SEPAY_WEBHOOK_SECRET: str | None = None
    SEPAY_BANK_NAME: str | None = None
    SEPAY_BANK_BIN: str | None = None
    SEPAY_BANK_ACCOUNT: str | None = None
    SEPAY_ACCOUNT_NAME: str | None = None
    SEPAY_PAYMENT_CODE_PREFIX: str = "GJOB"
    PAYMENT_ORDER_TTL_MINUTES: int = Field(default=30, ge=5, le=120)
    CV_UPLOAD_STORAGE_ROOT: str = "uploads"
    CV_UPLOAD_MAX_BYTES: int = 10 * 1024 * 1024
    CV_EXTRACTED_TEXT_MAX_CHARACTERS: int = Field(default=200_000, ge=1_000, le=2_000_000)
    CV_PHOTO_MAX_BYTES: int = 5 * 1024 * 1024
    CV_PHOTO_MAX_DIMENSION: int = 4096
    # Trong Settings (dù kế thừa BaseSettings hay class thường):
    ai_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    ai_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    ai_max_retries: int = Field(default=2, ge=0, le=5)
    ollama_llm_model: str = "qwen3:8b"
    ollama_llm_timeout_seconds: float = Field(default=165.0, gt=0, le=180)
    ollama_llm_num_ctx: int = Field(default=10240, ge=1024, le=131_072)
    ollama_llm_num_predict: int = Field(default=4608, ge=1, le=8192)
    ollama_llm_safety_margin: int = Field(default=256, ge=1, le=2048)
    cv_extraction_total_timeout_seconds: float = Field(default=230.0, gt=0, le=230)
    cv_extraction_correction_min_seconds: float = Field(default=60.0, gt=0, le=150)
    cv_extraction_network_margin_seconds: float = Field(default=20.0, ge=10, le=60)
    cv_repair_num_predict: int = Field(default=1024, ge=1, le=1024)
    cv_repair_provider_timeout_seconds: float = Field(default=40.0, gt=0, le=40)
    cv_repair_execution_timeout_seconds: float = Field(default=50.0, gt=0, le=50)
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    embedding_num_ctx: int = Field(default=8192,ge=1024,le=8192)
    embedding_num_batch: int = Field(default=4096,ge=1024,le=4096)
    ollama_base_url: str = "http://localhost:11434"
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    ranking_cache_root: str = ".cache/recruiter-ranking"
    ranking_model_digest: str = "7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab"

    @field_validator(
        "embedding_provider",
        "embedding_model",
        "ollama_base_url",
        "ollama_llm_model",
        mode="before",
    )
    @classmethod
    def validate_non_blank_embedding_setting(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Embedding settings cannot be blank.")
        return value.strip()

    @field_validator("SEPAY_PAYMENT_CODE_PREFIX", mode="before")
    @classmethod
    def validate_payment_code_prefix(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("SEPAY_PAYMENT_CODE_PREFIX must be a string.")
        normalized = value.strip().upper()
        if not normalized or not normalized.isalnum() or len(normalized) > 12:
            raise ValueError("SEPAY_PAYMENT_CODE_PREFIX must be 1-12 uppercase letters or digits.")
        return normalized

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
