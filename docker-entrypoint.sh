#!/bin/bash
set -e

echo "Starting CodeDox Docker entrypoint..."

# Fix permissions for logs directory mounted from host
if [ -d "/app/logs" ]; then
  echo "Setting permissions for logs directory..."
  sudo chown -R codedox:codedox /app/logs 2>/dev/null || true
  sudo chmod -R 755 /app/logs 2>/dev/null || true
fi

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

# Run migrations to handle schema updates
echo "Checking for schema updates..."
if [ -f "migrate.py" ]; then
  echo "Running database migrations..."
  python migrate.py || {
    echo "WARNING: Migration failed but continuing. Check logs if issues occur."
  }
else
  echo "No migration script found, skipping migrations."
fi

# Check for required environment variables
if [ -z "$CODE_LLM_API_KEY" ]; then
  echo "WARNING: No API key found. Please set CODE_LLM_API_KEY in .env"
  echo "The system will start but LLM features won't work without an API key."
fi

echo "Starting application..."
exec "$@"