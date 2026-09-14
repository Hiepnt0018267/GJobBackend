import pytest
from sqlalchemy.orm import Session

from app.core import database as database_module
from app.core.config import settings
from app.core.test_database import (
    DatabaseSafetyError,
    database_identity,
    validate_test_database_url,
)
from app.main import app


DEV_URL = "postgresql+psycopg://dev:secret@localhost:5433/gjob_db"


def test_test_database_url_is_required() -> None:
    with pytest.raises(DatabaseSafetyError, match="TEST_DATABASE_URL is required"):
        validate_test_database_url(DEV_URL, None)


def test_test_database_url_cannot_target_development_identity() -> None:
    same_database_with_other_credentials = (
        "postgresql+psycopg://other:other@127.0.0.1:5433/gjob_db"
    )
    with pytest.raises(DatabaseSafetyError, match="development database"):
        validate_test_database_url(DEV_URL, same_database_with_other_credentials)

    same_database_through_another_host = (
        "postgresql+psycopg://other:other@database.internal:5433/gjob_db"
    )
    with pytest.raises(DatabaseSafetyError, match="development database"):
        validate_test_database_url(DEV_URL, same_database_through_another_host)


def test_test_database_name_requires_exact_test_suffix() -> None:
    unsafe_name = "postgresql+psycopg://test:secret@localhost:5433/gjob_testing"
    with pytest.raises(DatabaseSafetyError, match="end with '_test'"):
        validate_test_database_url(DEV_URL, unsafe_name)


def test_pytest_session_uses_dedicated_guarded_engine() -> None:
    assert database_identity(database_module.engine.url).database.endswith("_test")
    assert database_identity(database_module.engine.url) != database_identity(settings.DATABASE_URL)

    db = database_module.SessionLocal()
    try:
        assert db.get_bind() is database_module.engine
    finally:
        db.close()


def test_fastapi_dependency_override_uses_test_session() -> None:
    override = app.dependency_overrides[database_module.get_db]
    dependency = override()
    db = next(dependency)
    try:
        assert isinstance(db, Session)
        assert db.get_bind() is database_module.engine
    finally:
        with pytest.raises(StopIteration):
            next(dependency)
