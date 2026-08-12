"""
Database configuration and session management using async SQLAlchemy.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy import MetaData, event, text
from typing import AsyncGenerator
import logging

from app.config import settings

logger = logging.getLogger(__name__)


# Build connection args with search_path for schema support
connect_args = {}
if settings.database_schema and settings.database_schema != "public":
    # Set search_path to include our schema first, then public
    connect_args["server_settings"] = {
        "search_path": f"{settings.database_schema},public"
    }

# Async Engine:
# - pool_pre_ping=True: Testet Verbindungen vor Nutzung, um "stale connection"-Fehler
#   nach Datenbank-Neustarts zu vermeiden
# - pool_size=10: Basis-Pool fuer normale Last (Uvicorn-Worker * gleichzeitige Requests)
# - max_overflow=20: Erlaubt bis zu 30 gleichzeitige Verbindungen bei Lastspitzen,
#   danach werden neue Requests blockiert bis eine Verbindung freigegeben wird
# - echo=settings.debug: SQL-Logging nur im Debug-Modus, um Production-Logs sauber zu halten
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args,
)

# Session Factory:
# - expire_on_commit=False: ORM-Objekte bleiben nach commit() lesbar, ohne eine neue
#   DB-Abfrage auszuloesen -- wichtig fuer FastAPI-Responses nach dem Commit
# - autocommit=False, autoflush=False: Explizite Kontrolle ueber Transaktionen
#   (commit/flush im CRUD oder Service); verhindert ungewollte Auto-Commits
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# MetaData mit Schema-Binding -- nur fuer nicht-public Schemas, da PostgreSQL
# bei Reflection den 'public'-Prefix nie zurueckgibt. MetaData(schema='public') wuerde
# FK-Targets auf 'public.table' auflösen, die DB gibt aber 'table' zurueck
# → endlose FK-Drop/Create-Schleife in Alembic autogenerate.
_sa_schema = settings.database_schema if settings.database_schema != "public" else None
metadata = MetaData(schema=_sa_schema)


class Base(declarative_base(metadata=metadata)):
    """
    Base class for all SQLAlchemy models.

    Provides common configuration for model classes.
    """
    # Required for Python 3.14+ compatibility with SQLAlchemy type annotations
    __allow_unmapped__ = True
    __abstract__ = True


# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields database sessions.

    Usage in FastAPI endpoints:
        @router.get("/users")
        async def list_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ============================================================================
# Audit Session Listener
# ============================================================================


@event.listens_for(Session, "after_begin")
def receive_after_begin(session, transaction, connection):
    """
    Session listener that injects audit context into PostgreSQL session variables.

    This listener is called after a transaction begins. It sets a session-local
    variable 'audit.current_actor_id' that can be accessed by database triggers
    or functions for audit logging purposes.

    The session variable is automatically cleared when the transaction ends.

    Usage in PostgreSQL triggers:
        CREATE TRIGGER audit_trigger
        BEFORE INSERT OR UPDATE ON some_table
        FOR EACH ROW
        EXECUTE FUNCTION audit_function();

        -- In audit_function():
        SELECT current_setting('audit.current_actor_id', true) INTO actor_id;

    Args:
        session: The SQLAlchemy session
        transaction: The transaction being started
        connection: The database connection
    """
    from app.core.context import get_actor_id

    # Get current actor ID from request context
    actor_id = get_actor_id()

    # If we have an actor ID, set it in the PostgreSQL session
    if actor_id:
        try:
            # Use synchronous connection for the SET LOCAL command
            # SET LOCAL ensures the variable is cleared after transaction ends
            sync_conn = connection.sync_connection
            sync_conn.execute(
                text(f"SET LOCAL audit.current_actor_id = '{actor_id}'")
            )
            logger.debug(f"Set audit.current_actor_id to {actor_id}")
        except Exception as e:
            # Don't fail the transaction if audit setup fails
            logger.warning(f"Failed to set audit.current_actor_id: {e}")
    else:
        logger.debug("No actor_id in context, skipping audit session variable")
