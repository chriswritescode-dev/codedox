#!/usr/bin/env python3
"""
Unified migration script for CodeDox database.
Reads PostgreSQL connection settings from environment and applies all migrations.
Uses Python psycopg library for all database operations.
"""

import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add src to path for config import
sys.path.insert(0, str(Path(__file__).parent))

# Import psycopg
try:
    import psycopg
    from psycopg import sql
except ImportError:
    print("ERROR: psycopg not found. Please install with: pip install psycopg[binary,pool]")
    sys.exit(1)


# Simple .env parser to avoid dependencies
def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:  # Don't override existing env vars
                        os.environ[key] = value


# Load .env file
load_env()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Handles database migrations for CodeDox."""

    # Define migrations in order
    MIGRATIONS = [
        # Core schema (always first)
        ("001_initial_schema", "src/database/schema.sql"),
        # Early migrations
        ("002_remove_page_links", "src/database/migrations/002_remove_page_links.sql"),
        ("003_add_markdown_content", "src/database/migrations/003_add_markdown_content.sql"),
        # Feature additions
        ("004_add_snippet_relationships", "src/database/migrations/add_snippet_relationships.sql"),
        ("005_add_upload_support", "migrations/add_upload_support.sql"),
        ("006_add_version_support", "src/database/migrations/006_add_version_support.sql"),
        # Search enhancements
        ("007_add_markdown_fulltext_search", "migrations/add_markdown_fulltext_search.sql"),
        # Source-scoped duplicate detection
        ("008_remove_code_hash_unique", "src/database/migrations/008_remove_code_hash_unique.sql"),
    ]

    def __init__(self):
        """Initialize migration runner with settings from environment."""
        # Read database config from environment
        self.db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "database": os.getenv("DB_NAME", "codedox"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgres"),
        }

    def get_connection(self, database: Optional[str] = None) -> psycopg.Connection:
        """Get a database connection."""
        from urllib.parse import quote_plus

        config = self.db_config.copy()
        if database:
            config["database"] = database

        # URL-encode the password to handle special characters
        encoded_password = quote_plus(str(config["password"]))
        conn_str = f"postgresql://{config['user']}:{encoded_password}@{config['host']}:{config['port']}/{config['database']}"
        return psycopg.connect(conn_str)

    def run_sql(self, sql: str, database: Optional[str] = None) -> tuple[bool, str]:
        """Run SQL query and return success status and output."""
        try:
            with self.get_connection(database) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    if cur.description:  # Has result set
                        result = cur.fetchall()
                        # Format result like psql output
                        output = "\n".join(str(row) for row in result)
                    else:
                        conn.commit()
                        output = "Query executed successfully"
                    return True, output
        except Exception as e:
            return False, str(e)

    def run_sql_file(self, filepath: str, database: Optional[str] = None) -> tuple[bool, str]:
        """Run SQL from a file."""
        try:
            if not os.path.exists(filepath):
                return False, f"File not found: {filepath}"

            with open(filepath, "r") as f:
                sql_content = f.read()

            # Execute the whole file
            with self.get_connection(database) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_content)
                    conn.commit()
                    return True, "Migration file executed successfully"
        except Exception as e:
            return False, str(e)

    def ensure_database_exists(self):
        """Ensure the CodeDox database exists."""
        try:
            with self.get_connection("postgres") as conn:
                # CREATE DATABASE requires autocommit mode
                conn.autocommit = True
                with conn.cursor() as cur:
                    # Check if database exists
                    cur.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s",
                        (self.db_config["database"],),
                    )
                    if cur.fetchone():
                        logger.info(f"Database '{self.db_config['database']}' already exists.")
                    else:
                        # Create database
                        logger.info(f"Creating database '{self.db_config['database']}'...")
                        cur.execute(
                            sql.SQL("CREATE DATABASE {}").format(
                                sql.Identifier(self.db_config["database"])
                            )
                        )
                        logger.info("Database created successfully!")
        except psycopg.OperationalError as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise Exception(f"Cannot connect to PostgreSQL server: {e}")
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            raise Exception(f"Database creation failed: {e}")

    def ensure_migrations_table(self):
        """Ensure the migrations tracking table exists."""
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_id VARCHAR(255) UNIQUE NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                applied_at TIMESTAMP DEFAULT NOW(),
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT
            )
        """

        success, output = self.run_sql(create_table_sql)
        if success:
            logger.info("Migrations table ready.")
        else:
            logger.error(f"Failed to create migrations table: {output}")
            raise Exception("Failed to create migrations table")

    def get_file_checksum(self, filepath: str) -> str:
        """Calculate MD5 checksum of a file."""
        md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def is_migration_applied(self, migration_id: str, checksum: str) -> tuple[bool, bool]:
        """
        Check if a migration has been applied.

        Returns:
            Tuple of (is_applied, has_changed)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT checksum FROM schema_migrations WHERE migration_id = %s AND success = TRUE",
                        (migration_id,),
                    )
                    result = cur.fetchone()

                    if not result:
                        return False, False

                    stored_checksum = result[0]
                    has_changed = stored_checksum != checksum
                    return True, has_changed
        except Exception:
            return False, False

    def apply_migration(self, migration_id: str, filepath: str) -> bool:
        """Apply a single migration file."""
        logger.info(f"Checking migration: {migration_id}")

        # Check if file exists
        if not os.path.exists(filepath):
            logger.warning(f"Migration file not found: {filepath}")
            return False

        # Calculate checksum
        checksum = self.get_file_checksum(filepath)

        # Check if already applied
        is_applied, has_changed = self.is_migration_applied(migration_id, checksum)

        if is_applied and not has_changed:
            logger.info(f"  ✓ Already applied: {migration_id}")
            return True

        if has_changed:
            logger.warning(f"  ⚠ Migration file changed since last run: {migration_id}")
            logger.warning(
                "  Consider creating a new migration instead of modifying existing ones."
            )

        # Apply migration
        logger.info(f"  → Applying migration: {migration_id}")
        success, output = self.run_sql_file(filepath)

        if success:
            # Record successful migration
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO schema_migrations (migration_id, checksum, success)
                            VALUES (%s, %s, TRUE)
                            ON CONFLICT (migration_id) 
                            DO UPDATE SET checksum = EXCLUDED.checksum, 
                                         applied_at = NOW(),
                                         success = TRUE,
                                         error_message = NULL
                            """,
                            (migration_id, checksum),
                        )
                        conn.commit()
                logger.info(f"  ✓ Successfully applied: {migration_id}")
                return True
            except Exception as e:
                logger.error(f"  ✗ Failed to record migration: {e}")
                return False
        else:
            logger.error(f"  ✗ Failed to apply {migration_id}: {output}")

            # Record failed migration
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO schema_migrations (migration_id, checksum, success, error_message)
                            VALUES (%s, %s, FALSE, %s)
                            ON CONFLICT (migration_id) 
                            DO UPDATE SET checksum = EXCLUDED.checksum,
                                         applied_at = NOW(),
                                         success = FALSE,
                                         error_message = EXCLUDED.error_message
                            """,
                            (migration_id, checksum, output),
                        )
                        conn.commit()
            except Exception as e:
                logger.error(f"Failed to record failed migration: {e}")

            raise Exception(f"Migration failed: {output}")

    def run_migrations(self, force: bool = False):
        """Run all pending migrations."""
        logger.info("Starting CodeDox database migration...")
        logger.info(
            f"Database: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
        )

        # Ensure database exists
        self.ensure_database_exists()

        # Ensure migrations table exists
        self.ensure_migrations_table()

        # Run migrations in order
        success_count = 0
        skip_count = 0
        fail_count = 0

        for migration_id, filepath in self.MIGRATIONS:
            try:
                if self.apply_migration(migration_id, filepath):
                    success_count += 1
                else:
                    skip_count += 1
            except Exception:
                fail_count += 1
                if not force:
                    logger.error("Stopping due to migration failure. Use --force to continue.")
                    break

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Migration Summary:")
        logger.info(f"  Total migrations: {len(self.MIGRATIONS)}")
        logger.info(f"  Applied/Already applied: {success_count}")
        logger.info(f"  Skipped: {skip_count}")
        logger.info(f"  Failed: {fail_count}")
        logger.info("=" * 60)

        if fail_count > 0:
            sys.exit(1)

    def show_status(self):
        """Show migration status."""
        logger.info("Checking migration status...")

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if table exists
                    cur.execute(
                        "SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations'"
                    )
                    if not cur.fetchone():
                        logger.info("\nNo migrations have been run yet.")
                        logger.info(f"Total migrations defined: {len(self.MIGRATIONS)}")
                        return

                    # Get applied migrations
                    cur.execute(
                        """
                        SELECT migration_id, checksum, applied_at, success, error_message
                        FROM schema_migrations
                        ORDER BY applied_at DESC
                        """
                    )
                    applied_rows = cur.fetchall()

                    logger.info(
                        f"\nDatabase: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
                    )
                    logger.info(f"Total migrations defined: {len(self.MIGRATIONS)}")
                    logger.info(f"Migrations in database: {len(applied_rows)}\n")

                    # Check each migration
                    logger.info("Migration Status:")
                    logger.info("-" * 80)

                    for migration_id, filepath in self.MIGRATIONS:
                        if os.path.exists(filepath):
                            current_checksum = self.get_file_checksum(filepath)

                            # Find in applied migrations
                            applied_migration = next(
                                (m for m in applied_rows if m[0] == migration_id), None
                            )

                            if applied_migration:
                                _, stored_checksum, applied_at, success, error = applied_migration

                                if success:
                                    if current_checksum == stored_checksum:
                                        status = "✓ Applied"
                                    else:
                                        status = "⚠ Modified"
                                else:
                                    status = "✗ Failed"

                                logger.info(f"{migration_id:<30} {status:<12} {applied_at}")
                                if error:
                                    logger.info(f"  Error: {error}")
                            else:
                                logger.info(f"{migration_id:<30} ○ Pending")
                        else:
                            logger.info(f"{migration_id:<30} ✗ File missing: {filepath}")

                    logger.info("-" * 80)
        except Exception as e:
            logger.error(f"Failed to check status: {e}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="CodeDox Database Migration Tool")
    parser.add_argument(
        "command",
        choices=["migrate", "status"],
        nargs="?",
        default="migrate",
        help="Command to run (default: migrate)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Continue running migrations even if one fails"
    )

    args = parser.parse_args()

    try:
        runner = MigrationRunner()

        if args.command == "status":
            runner.show_status()
        else:
            runner.run_migrations(force=args.force)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
