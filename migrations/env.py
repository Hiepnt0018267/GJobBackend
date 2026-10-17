from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# â”€â”€ Project imports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Import settings so DATABASE_URL comes from .env (never hard-coded here)
from app.core.config import settings

# Import Base + all models so autogenerate can detect them
from app.core.database import Base
import app.models.user  # noqa: F401 -- registers User table with Base.metadata
import app.models.job   # noqa: F401 -- registers Job table with Base.metadata
import app.models.recruiter_profile  # noqa: F401 -- registers RecruiterProfile table
import app.models.cv  # noqa: F401 -- registers CV table
import app.models.cv_extraction  # noqa: F401 -- registers CV extraction attempts
import app.models.cv_template  # noqa: F401 -- registers CVTemplate table
import app.models.application  # noqa: F401 -- registers JobApplication table
import app.models.application_status_history  # noqa: F401 -- registers application history
import app.models.admin_audit_log  # noqa: F401 -- registers admin audit logs
import app.models.skill  # noqa: F401 -- registers skill taxonomy and job links
import app.models.cv_job_match  # noqa: F401 -- registers derived CV/Job matches
import app.models.notification  # noqa: F401 -- registers shared notifications
import app.models.subscription  # noqa: F401 -- registers subscription catalog and history
import app.models.payment  # noqa: F401 -- registers payment orders and provider transactions

# â”€â”€ Alembic Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
config = context.config

# Override sqlalchemy.url from environment (not from alembic.ini plain text)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

