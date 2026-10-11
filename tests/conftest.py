from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import settings
from app.core.test_database import (
    DatabaseSafetyError,
    database_identity,
    safe_database_label,
    validate_test_database_url,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_DATABASE_URL = settings.DATABASE_URL

try:
    TEST_DATABASE_URL = validate_test_database_url(
        DEVELOPMENT_DATABASE_URL,
        settings.TEST_DATABASE_URL,
    )
except DatabaseSafetyError as exc:
    raise pytest.UsageError(str(exc)) from exc


from app.core import database as database_module  # noqa: E402


development_engine = database_module.engine
test_engine = database_module.create_database_engine(
    TEST_DATABASE_URL.render_as_string(hide_password=False)
)
TestingSessionLocal = database_module.create_session_factory(test_engine)
database_module.engine = test_engine
database_module.SessionLocal = TestingSessionLocal
development_engine.dispose()


def _assert_active_test_database() -> None:
    if database_module.engine is not test_engine:
        raise pytest.UsageError("The application engine is not the guarded pytest engine.")
    if database_identity(database_module.engine.url) != database_identity(TEST_DATABASE_URL):
        raise pytest.UsageError("The active pytest engine no longer targets TEST_DATABASE_URL.")
    if database_identity(database_module.engine.url) == database_identity(DEVELOPMENT_DATABASE_URL):
        raise pytest.UsageError("The active pytest engine targets the development database.")


def _upgrade_test_schema() -> None:
    original_url = settings.DATABASE_URL
    settings.DATABASE_URL = TEST_DATABASE_URL.render_as_string(hide_password=False)
    try:
        alembic_config = Config(str(PROJECT_ROOT / "alembic.ini"))
        command.upgrade(alembic_config, "head")
    finally:
        settings.DATABASE_URL = original_url


_assert_active_test_database()
try:
    with test_engine.connect() as connection:
        actual_database = connection.execute(text("SELECT current_database()")).scalar_one()
except Exception as exc:
    raise pytest.UsageError(
        f"Cannot connect to guarded test database {safe_database_label(TEST_DATABASE_URL)}."
    ) from exc

if actual_database.lower() != database_identity(TEST_DATABASE_URL).database:
    raise pytest.UsageError("PostgreSQL connected to an unexpected database; aborting pytest.")

_upgrade_test_schema()


from app.main import app  # noqa: E402


def override_get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[database_module.get_db] = override_get_test_db


def pytest_report_header() -> str:
    return f"guarded test database: {safe_database_label(TEST_DATABASE_URL)}"


def pytest_runtest_setup() -> None:
    _assert_active_test_database()


@pytest.fixture(autouse=True)
def isolate_ranking_lifecycle(monkeypatch, tmp_path):
    """New lifecycle hooks must never contact a live embedding server in pytest.

    Focused ranking tests exercise precompute separately with synthetic providers.
    """
    from app.routers import cvs, recruiters
    async def no_live_precompute(*args, **kwargs):
        return None
    monkeypatch.setattr(cvs, "precompute_entity", no_live_precompute)
    monkeypatch.setattr(recruiters, "precompute_entity", no_live_precompute)
    monkeypatch.setattr(settings, "ranking_cache_root", str(tmp_path / "ranking"))


def pytest_sessionfinish() -> None:
    app.dependency_overrides.pop(database_module.get_db, None)
    test_engine.dispose()
