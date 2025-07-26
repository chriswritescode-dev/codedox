#!/bin/bash
set -e

echo "Starting CodeDox Docker entrypoint..."

# Wait for PostgreSQL to be ready using Python
echo "Waiting for PostgreSQL..."
until python3 -c 'import psycopg, os, sys; conn = psycopg.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"]); conn.close()' 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is ready!"

# Check if database is already initialized using Python
python3 -c 'import psycopg, os; conn = psycopg.connect(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"], dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"]); cur = conn.cursor(); cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = '\''code_snippets'\''"); result = cur.fetchone(); cur.close(); conn.close(); exit(0 if result else 1)' || {
  echo "Initializing database..."
  python cli.py init
  echo "Database initialization complete!"
}

# Check for required environment variables
if [ -z "$CODE_LLM_API_KEY" ]; then
  echo "WARNING: No API key found. Please set CODE_LLM_API_KEY in .env"
  echo "The system will start but LLM features won't work without an API key."
fi

# Run any pending migrations (if we add migration support in the future)
# python -m alembic upgrade head

echo "Starting application..."
exec "$@"