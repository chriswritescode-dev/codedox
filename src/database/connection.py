"""Database connection and session management."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str | None = None):
        """Initialize database manager.

        Args:
            database_url: PostgreSQL connection URL. If not provided, uses settings.
        """
        if database_url:
            self.database_url = database_url
        else:
            settings = get_settings()
            self.database_url = settings.database.url

        # Create engine with connection pooling
        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=20,  # Increased from 10
            max_overflow=30,  # Increased from 20
            pool_timeout=30,  # Wait max 30 seconds for connection
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False,  # Set to True for SQL debugging
        )

        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def init_db(self, drop_existing: bool = False) -> None:
        """Initialize database schema.

        Args:
            drop_existing: If True, drops all tables before creating.
        """
        try:
            # Create extensions first
            with self.engine.connect() as conn:
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm"'))
                conn.commit()

            # Check if tables already exist
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('crawl_jobs', 'documents', 'code_snippets')
                """)
                )
                table_count = result.scalar() or 0

                if table_count > 0 and not drop_existing:
                    logger.info(f"Database already initialized ({table_count} tables exist)")
                    return

            # Check if schema.sql exists
            import os

            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

            if os.path.exists(schema_path):
                if drop_existing:
                    logger.warning("Dropping existing tables...")
                    with self.engine.connect() as conn:
                        conn.execute(text("DROP TABLE IF EXISTS code_snippets CASCADE"))
                        conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
                        conn.execute(text("DROP TABLE IF EXISTS crawl_jobs CASCADE"))
                        conn.commit()

                logger.info("Using schema.sql for database initialization...")
                self.execute_sql_file(schema_path)
            else:
                # Fallback to SQLAlchemy models
                if drop_existing:
                    logger.warning("Dropping all existing tables...")
                    Base.metadata.drop_all(bind=self.engine)

                logger.info("Creating database tables from models...")
                Base.metadata.create_all(bind=self.engine)

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope for database operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def execute_sql_file(self, filepath: str) -> None:
        """Execute SQL commands from a file.

        Args:
            filepath: Path to SQL file
        """
        with open(filepath) as f:
            sql_content = f.read()

        with self.engine.connect() as conn:
            # Split by semicolon but be careful with functions/procedures
            statements = []
            current = []
            in_function = False
            in_generated_column = False

            for line in sql_content.split("\n"):
                # Skip comments
                if line.strip().startswith("--"):
                    continue

                if "CREATE OR REPLACE FUNCTION" in line or "CREATE FUNCTION" in line:
                    in_function = True
                elif "GENERATED ALWAYS AS" in line:
                    in_generated_column = True
                elif line.strip() == "$$ LANGUAGE plpgsql;":
                    in_function = False
                    current.append(line)
                    statements.append("\n".join(current))
                    current = []
                    continue
                elif in_generated_column and ") STORED" in line:
                    in_generated_column = False

                current.append(line)

                if not in_function and not in_generated_column and line.strip().endswith(";"):
                    statements.append("\n".join(current))
                    current = []

            # Execute each statement
            for statement in statements:
                if statement.strip():
                    try:
                        conn.execute(text(statement))
                    except Exception as e:
                        logger.error(f"Error executing SQL: {e}")
                        logger.error(f"Statement: {statement[:100]}...")
                        raise

            conn.commit()

    def test_connection(self) -> bool:
        """Test database connection.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False


# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get or create the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get database session."""
    db_manager = get_db_manager()
    with db_manager.session_scope() as session:
        yield session


def get_session() -> Session:
    """Get a new database session."""
    return get_db_manager().get_session()


def init_db(drop_existing: bool = False) -> None:
    """Initialize the database."""
    db_manager = get_db_manager()
    db_manager.init_db(drop_existing=drop_existing)
