"""Migration check utility for automatic migration detection and application."""

import logging
import os
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from migrate import MigrationRunner

logger = logging.getLogger(__name__)


def check_pending_migrations() -> tuple[bool, list[str]]:
    """
    Check if there are pending migrations.

    Returns:
        Tuple of (has_pending, list_of_pending_migration_ids)
    """
    try:
        runner = MigrationRunner()

        # Check if migrations table exists
        check_table_sql = (
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations'"
        )

        # Direct psycopg query for better control
        try:
            with runner.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(check_table_sql)
                    result = cur.fetchone()

                    # If no table, all migrations are pending
                    if not result:
                        pending = [m[0] for m in runner.MIGRATIONS]
                        return len(pending) > 0, pending
        except Exception as e:
            logger.warning(f"Could not check migrations table: {e}")
            return False, []

        # Get applied migrations
        try:
            with runner.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT migration_id, checksum, success FROM schema_migrations")
                    rows = cur.fetchall()

                    # Extract successful migration IDs
                    applied_ids = set()
                    for row in rows:
                        migration_id, checksum, success = row
                        if success:  # Only count successful
                            applied_ids.add(migration_id)

                    # Find pending migrations
                    pending = []
                    for migration_id, filepath in runner.MIGRATIONS:
                        if migration_id not in applied_ids:
                            if os.path.exists(filepath):
                                pending.append(migration_id)

                    return len(pending) > 0, pending

        except Exception as e:
            logger.warning(f"Failed to query migrations: {e}")
            return False, []

    except Exception as e:
        logger.warning(f"Could not check migrations: {e}")
        return False, []


def auto_apply_migrations() -> bool:
    """
    Automatically apply pending migrations.

    Returns:
        True if migrations were applied successfully or none were needed
    """
    try:
        has_pending, pending_migrations = check_pending_migrations()

        if not has_pending:
            logger.info("No pending migrations found")
            return True

        print("\n" + "=" * 70)
        print("📦 APPLYING DATABASE MIGRATIONS")
        print("=" * 70)
        print(f"\nFound {len(pending_migrations)} pending migration(s):")
        for migration in pending_migrations:
            print(f"  • {migration}")
        print()

        # Run migrations
        runner = MigrationRunner()
        runner.run_migrations(force=False)

        # Check if all migrations were applied
        has_pending_after, still_pending = check_pending_migrations()

        if not has_pending_after:
            print("\n✅ All migrations applied successfully!")
            print("=" * 70 + "\n")
            return True
        else:
            print(f"\n⚠️  Some migrations could not be applied: {still_pending}")
            print("=" * 70 + "\n")
            return False

    except Exception as e:
        print(f"\n❌ Error applying migrations: {e}")
        print("Please run 'python migrate.py migrate' manually to see detailed errors.")
        print("=" * 70 + "\n")
        return False


def print_migration_warning(pending_migrations: list[str]):
    """Print a warning about pending migrations."""
    print("\n" + "=" * 70)
    print("⚠️  PENDING DATABASE MIGRATIONS DETECTED")
    print("=" * 70)
    print(f"\nThere are {len(pending_migrations)} pending migration(s):")
    for migration in pending_migrations:
        print(f"  • {migration}")
    print("\nTo apply migrations, run:")
    print("  python migrate.py migrate")
    print("\nThe application will continue, but may not function correctly.")
    print("=" * 70 + "\n")
