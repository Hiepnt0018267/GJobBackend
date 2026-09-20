# pyrefly: ignore [missing-import]
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
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
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    ollama_base_url: str = "http://localhost:11434"
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    @field_validator(
        "embedding_provider",
        "embedding_model",
        "ollama_base_url",
        mode="before",
    )
    @classmethod
    def validate_non_blank_embedding_setting(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Embedding settings cannot be blank.")
        return value.strip()

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
