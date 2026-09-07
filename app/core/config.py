# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CV_UPLOAD_STORAGE_ROOT: str = "uploads"
    CV_UPLOAD_MAX_BYTES: int = 10 * 1024 * 1024
    CV_PHOTO_MAX_BYTES: int = 5 * 1024 * 1024
    CV_PHOTO_MAX_DIMENSION: int = 4096

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
