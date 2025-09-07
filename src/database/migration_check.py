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
        success, output = runner.run_psql(check_table_sql)
        
        # If table doesn't exist, all migrations are pending
        if not success or "0 rows" in output:
            pending = [m[0] for m in runner.MIGRATIONS]
            return len(pending) > 0, pending
        
        # Get applied migrations
        query_sql = "SELECT migration_id, checksum, success FROM schema_migrations"
        success, output = runner.run_psql(query_sql)
        
        if not success:
            logger.warning(f"Failed to check migrations: {output}")
            return False, []
        
        # Parse applied migrations
        applied_ids = set()
        lines = output.strip().split("\n")
        in_data = False
        for line in lines:
            if "---" in line and not in_data:
                in_data = True
                continue
            if in_data and "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3 and parts[2].lower() == "t":  # Only count successful
                    applied_ids.add(parts[0])
        
        # Check for pending migrations
        pending = []
        for migration_id, filepath in runner.MIGRATIONS:
            if migration_id not in applied_ids:
                if os.path.exists(filepath):
                    pending.append(migration_id)
        
        return len(pending) > 0, pending
        
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