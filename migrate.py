#!/usr/bin/env python3
"""
Unified migration script for CodeDox database.
Reads PostgreSQL connection settings from .env file and applies all migrations.
Uses psql command-line tool to avoid Python dependencies.
"""

import hashlib
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add src to path for config import
sys.path.insert(0, str(Path(__file__).parent))

# Simple .env parser to avoid dependencies
def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value

# Load .env file
load_env()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Handles database migrations for CodeDox."""

    # Define migrations in order
    MIGRATIONS = [
        # Core schema (always first)
        ('001_initial_schema', 'src/database/schema.sql'),

        # Early migrations
        ('002_remove_page_links', 'src/database/migrations/002_remove_page_links.sql'),
        ('003_add_markdown_content', 'src/database/migrations/003_add_markdown_content.sql'),

        # Feature additions
        ('004_add_snippet_relationships', 'src/database/migrations/add_snippet_relationships.sql'),
        ('005_add_upload_support', 'migrations/add_upload_support.sql'),
    ]

    def __init__(self):
        """Initialize migration runner with settings from .env."""
        # Read database config from environment
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'codedox'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }

    def run_psql(self, sql: str, database: str | None = None) -> tuple[bool, str]:
        """Run SQL using psql command."""
        db = database or self.db_config['database']

        # Build psql command
        cmd = [
            'psql',
            '-h', self.db_config['host'],
            '-p', self.db_config['port'],
            '-U', self.db_config['user'],
            '-d', db,
            '-c', sql
        ]

        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = self.db_config['password']

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def run_psql_file(self, filepath: str, database: str | None = None) -> tuple[bool, str]:
        """Run SQL file using psql command."""
        db = database or self.db_config['database']

        # Build psql command
        cmd = [
            'psql',
            '-h', self.db_config['host'],
            '-p', self.db_config['port'],
            '-U', self.db_config['user'],
            '-d', db,
            '-f', filepath
        ]

        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = self.db_config['password']

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def ensure_database_exists(self):
        """Ensure the CodeDox database exists."""
        # Check if database exists
        check_sql = f"SELECT 1 FROM pg_database WHERE datname = '{self.db_config['database']}'"
        success, output = self.run_psql(check_sql, 'postgres')

        if success and '1 row' in output:
            logger.info(f"Database '{self.db_config['database']}' already exists.")
        else:
            # Create database
            logger.info(f"Creating database '{self.db_config['database']}'...")
            create_sql = f"CREATE DATABASE {self.db_config['database']}"
            success, output = self.run_psql(create_sql, 'postgres')

            if success:
                logger.info("Database created successfully!")
            else:
                logger.error(f"Failed to create database: {output}")
                raise Exception(f"Database creation failed: {output}")

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

        success, output = self.run_psql(create_table_sql)
        if success:
            logger.info("Migrations table ready.")
        else:
            logger.error(f"Failed to create migrations table: {output}")
            raise Exception("Failed to create migrations table")

    def get_file_checksum(self, filepath: str) -> str:
        """Calculate MD5 checksum of a file."""
        md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def is_migration_applied(self, migration_id: str, checksum: str) -> tuple[bool, bool]:
        """
        Check if a migration has been applied.
        
        Returns:
            Tuple of (is_applied, has_changed)
        """
        check_sql = f"SELECT checksum FROM schema_migrations WHERE migration_id = '{migration_id}' AND success = TRUE"
        success, output = self.run_psql(check_sql)

        if not success or '0 rows' in output:
            return False, False

        # Extract checksum from output
        lines = output.strip().split('\n')
        for line in lines:
            line = line.strip()
            if len(line) == 32 and all(c in '0123456789abcdef' for c in line):
                stored_checksum = line
                has_changed = stored_checksum != checksum
                return True, has_changed

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
            logger.warning("  Consider creating a new migration instead of modifying existing ones.")

        # Apply migration
        logger.info(f"  → Applying migration: {migration_id}")
        success, output = self.run_psql_file(filepath)

        if success:
            # Record successful migration
            record_sql = f"""
                INSERT INTO schema_migrations (migration_id, checksum, success)
                VALUES ('{migration_id}', '{checksum}', TRUE)
                ON CONFLICT (migration_id) 
                DO UPDATE SET checksum = EXCLUDED.checksum, 
                             applied_at = NOW(),
                             success = TRUE,
                             error_message = NULL
            """
            self.run_psql(record_sql)
            logger.info(f"  ✓ Successfully applied: {migration_id}")
            return True
        else:
            logger.error(f"  ✗ Failed to apply {migration_id}: {output}")

            # Record failed migration
            error_msg = output.replace("'", "''")  # Escape single quotes
            record_sql = f"""
                INSERT INTO schema_migrations (migration_id, checksum, success, error_message)
                VALUES ('{migration_id}', '{checksum}', FALSE, '{error_msg}')
                ON CONFLICT (migration_id) 
                DO UPDATE SET checksum = EXCLUDED.checksum,
                             applied_at = NOW(),
                             success = FALSE,
                             error_message = EXCLUDED.error_message
            """
            self.run_psql(record_sql)

            raise Exception(f"Migration failed: {output}")

    def run_migrations(self, force: bool = False):
        """Run all pending migrations."""
        logger.info("Starting CodeDox database migration...")
        logger.info(f"Database: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")

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
        logger.info("\n" + "="*60)
        logger.info("Migration Summary:")
        logger.info(f"  Total migrations: {len(self.MIGRATIONS)}")
        logger.info(f"  Applied/Already applied: {success_count}")
        logger.info(f"  Skipped: {skip_count}")
        logger.info(f"  Failed: {fail_count}")
        logger.info("="*60)

        if fail_count > 0:
            sys.exit(1)

    def show_status(self):
        """Show migration status."""
        logger.info("Checking migration status...")

        # Check if migrations table exists
        check_table_sql = "SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations'"
        success, output = self.run_psql(check_table_sql)

        if not success or '0 rows' in output:
            logger.info("\nNo migrations have been run yet.")
            logger.info(f"Total migrations defined: {len(self.MIGRATIONS)}")
            return

        # Get applied migrations
        query_sql = """
            SELECT migration_id, checksum, applied_at, success, error_message
            FROM schema_migrations
            ORDER BY applied_at DESC
        """
        success, output = self.run_psql(query_sql)

        if not success:
            logger.error(f"Failed to query migrations: {output}")
            return

        # Parse output
        applied = []
        lines = output.strip().split('\n')
        in_data = False
        for line in lines:
            if '---' in line and not in_data:
                in_data = True
                continue
            if in_data and '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 5:
                    applied.append(parts)

        logger.info(f"\nDatabase: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
        logger.info(f"Total migrations defined: {len(self.MIGRATIONS)}")
        logger.info(f"Migrations in database: {len(applied)}\n")

        # Check each migration
        logger.info("Migration Status:")
        logger.info("-" * 80)

        for migration_id, filepath in self.MIGRATIONS:
            if os.path.exists(filepath):
                current_checksum = self.get_file_checksum(filepath)

                # Find in applied migrations
                applied_migration = next(
                    (m for m in applied if m[0] == migration_id),
                    None
                )

                if applied_migration:
                    _, stored_checksum, applied_at, success, error = applied_migration

                    if success.lower() == 't':
                        if current_checksum == stored_checksum:
                            status = "✓ Applied"
                        else:
                            status = "⚠ Modified"
                    else:
                        status = "✗ Failed"

                    logger.info(f"{migration_id:<30} {status:<12} {applied_at}")
                    if error and error != '':
                        logger.info(f"  Error: {error}")
                else:
                    logger.info(f"{migration_id:<30} ○ Pending")
            else:
                logger.info(f"{migration_id:<30} ✗ File missing: {filepath}")

        logger.info("-" * 80)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='CodeDox Database Migration Tool')
    parser.add_argument(
        'command',
        choices=['migrate', 'status'],
        nargs='?',
        default='migrate',
        help='Command to run (default: migrate)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Continue running migrations even if one fails'
    )

    args = parser.parse_args()

    try:
        runner = MigrationRunner()

        if args.command == 'status':
            runner.show_status()
        else:
            runner.run_migrations(force=args.force)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
