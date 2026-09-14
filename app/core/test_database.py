from dataclasses import dataclass

from sqlalchemy.engine import URL, make_url


class DatabaseSafetyError(RuntimeError):
    """Raised before pytest can connect to an unsafe database target."""


@dataclass(frozen=True)
class DatabaseIdentity:
    host: str
    port: int
    database: str


def _normalized_host(host: str | None) -> str:
    normalized = (host or "localhost").strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return "loopback"
    return normalized


def database_identity(url: str | URL) -> DatabaseIdentity:
    parsed = make_url(url) if isinstance(url, str) else url
    database = (parsed.database or "").strip()
    if not database:
        raise DatabaseSafetyError("Database URL must include a database name.")
    return DatabaseIdentity(
        host=_normalized_host(parsed.host),
        port=parsed.port or 5432,
        database=database.lower(),
    )


def validate_test_database_url(
    development_url: str,
    test_url: str | None,
) -> URL:
    if not test_url or not test_url.strip():
        raise DatabaseSafetyError(
            "TEST_DATABASE_URL is required when running pytest; refusing to use DATABASE_URL."
        )

    try:
        development = make_url(development_url)
        test = make_url(test_url)
    except Exception as exc:
        raise DatabaseSafetyError(
            "DATABASE_URL and TEST_DATABASE_URL must be valid SQLAlchemy URLs."
        ) from exc

    if not development.get_backend_name().startswith("postgresql"):
        raise DatabaseSafetyError("DATABASE_URL must target PostgreSQL.")
    if not test.get_backend_name().startswith("postgresql"):
        raise DatabaseSafetyError("TEST_DATABASE_URL must target PostgreSQL.")

    development_identity = database_identity(development)
    test_identity = database_identity(test)
    if (
        development_identity == test_identity
        or development_identity.database == test_identity.database
    ):
        raise DatabaseSafetyError(
            "TEST_DATABASE_URL targets the development database; refusing to run pytest."
        )
    if not test_identity.database.endswith("_test"):
        raise DatabaseSafetyError(
            "The test database name must end with '_test'."
        )
    return test


def safe_database_label(url: str | URL) -> str:
    identity = database_identity(url)
    return f"{identity.database}@{identity.host}:{identity.port}"
