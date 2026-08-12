import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, text
from sqlalchemy import pool

from alembic import context

# Add backend directory to path to import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import database Base and settings
from app.database import Base
from app.config import settings

# Import all models for autogenerate to detect them
import app.models  # noqa: F401

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set SQLAlchemy URL from settings (use sync URL for Alembic)
database_url = os.getenv("DATABASE_URL") or settings.sync_database_url
config.set_main_option("sqlalchemy.url", database_url)
# Target metadata for autogenerate
target_metadata = Base.metadata

# Schema to use (from settings)
db_schema = settings.database_schema

# Function to filter out alembic_version table from autogenerate
def include_object(object, name, type_, reflected, compare_to):
    """Filter out alembic_version table from autogenerate."""
    if type_ == "table" and name == "alembic_version":
        return False
    return True

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=db_schema,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Schema name from environment config (settings.database_schema), not user input
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {db_schema}"))
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        connection.execute(text(f"SET search_path TO {db_schema}, public"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=db_schema,
            include_schemas=True,
        )

        with context.begin_transaction():
            # Set search_path again within the transaction
            # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
            connection.execute(text(f"SET search_path TO {db_schema}, public"))
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
