# CodeDox Database Migrations

This directory contains database migrations for CodeDox. Migrations are applied in a specific order to ensure database consistency.

## Requirements

- PostgreSQL `psql` command-line tool must be installed and in your PATH
- A `.env` file with database connection settings

## Usage

### Running Migrations

The `migrate.py` script automatically reads database connection settings from your `.env` file:

```bash
# Run all pending migrations
python migrate.py

# Or explicitly specify the command
python migrate.py migrate

# Continue even if a migration fails
python migrate.py migrate --force

# Check migration status
python migrate.py status
```

### Configuration

The script uses these environment variables from `.env`:
- `DB_HOST` - PostgreSQL host (default: localhost)
- `DB_PORT` - PostgreSQL port (default: 5432)
- `DB_NAME` - Database name (default: codedox)
- `DB_USER` - Database user (default: postgres)
- `DB_PASSWORD` - Database password

### Migration Order

Migrations are applied in this order:

1. **001_initial_schema** - Core database schema (`src/database/schema.sql`)
2. **002_remove_page_links** - Remove deprecated page_links table
3. **003_remove_markdown_content** - Remove markdown_content column
4. **004_add_snippet_relationships** - Add code snippet relationships
5. **005_add_upload_support** - Add support for file uploads

### Creating New Migrations

To add a new migration:

1. Create a new SQL file in the `migrations/` directory
2. Name it descriptively (e.g., `006_add_user_auth.sql`)
3. Add it to the `MIGRATIONS` list in `migrate.py`
4. Run `python migrate.py` to apply it

### Migration Tracking

The script tracks migrations in the `schema_migrations` table:
- Records which migrations have been applied
- Stores checksums to detect if migration files change
- Tracks success/failure status
- Prevents re-running successful migrations

### Best Practices

1. **Never modify existing migrations** - Create new ones instead
2. **Test migrations locally first** - Use a development database
3. **Make migrations idempotent** - Use `IF NOT EXISTS` clauses
4. **Keep migrations focused** - One logical change per migration
5. **Document breaking changes** - Add comments in the SQL file

### Troubleshooting

If a migration fails:

1. Check the error message in the output
2. Fix the issue in the SQL file
3. Run `python migrate.py` again
4. Use `python migrate.py status` to see which migrations succeeded

To reset and start fresh (WARNING: destroys all data):

```bash
# Drop and recreate database
psql -U postgres -c "DROP DATABASE IF EXISTS codedox"
psql -U postgres -c "CREATE DATABASE codedox"

# Run all migrations
python migrate.py
```