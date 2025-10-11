#!/bin/bash
set -e

echo "🚀 CodeDox Docker Setup Script"
echo "=============================="

USE_EXTERNAL_DB=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --external-db)
            USE_EXTERNAL_DB=true
            shift
            ;;
        --clean)
            CLEAN_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--external-db] [--clean]"
            echo "  --external-db: Use external PostgreSQL database (no local postgres container)"
            echo "  --clean: Clean up existing Docker resources before setup"
            exit 1
            ;;
    esac
done

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Docker is installed
if ! command_exists docker; then
    echo "❌ Docker is not installed. Please install Docker Desktop and try again."
    echo "   Visit: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Check if docker-compose is installed
if ! command_exists docker-compose; then
    echo "❌ docker-compose is not installed. Please install Docker Desktop and try again."
    echo "   Visit: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Select appropriate docker-compose file
if [ "$USE_EXTERNAL_DB" = true ]; then
    COMPOSE_FILE="docker-compose.external-db.yml"
    echo "📌 Using external PostgreSQL database"
else
    COMPOSE_FILE="docker-compose.yml"
    echo "📌 Using local PostgreSQL container"
fi

# Clean up any existing containers/volumes (optional)
if [ "$CLEAN_MODE" = true ]; then
    echo "🧹 Cleaning up existing Docker resources..."
    docker-compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
    docker system prune -f
fi

# Check if .env exists, create from .env.example if not
if [ ! -f .env ]; then
    if [ ! -f .env.example ]; then
        echo "❌ .env.example not found. Cannot create .env file."
        exit 1
    fi
    
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    
    echo ""
    echo "⚠️  IMPORTANT: You need to configure the .env file!"
    echo ""
    echo "   1. Open .env in your editor"
    echo "   2. Configure LLM settings:"
    echo "      - For OpenAI: Set CODE_LLM_API_KEY to your OpenAI API key"
    echo "      - For local LLMs: Also uncomment and set CODE_LLM_BASE_URL"
    echo ""
    echo "   Example for OpenAI:"
    echo "      CODE_LLM_API_KEY=sk-..."
    echo ""
    echo "   Example for local LLM (ollama, llama.cpp, lm studio):"
    echo "      CODE_LLM_API_KEY=your-local-key"
    echo "      CODE_LLM_BASE_URL=http://host.docker.internal:1337/v1"
    echo ""
    
    if [ "$USE_EXTERNAL_DB" = true ]; then
        echo "   3. Configure external PostgreSQL connection:"
        echo "      DB_HOST=your-postgres-host"
        echo "      DB_PORT=5432"
        echo "      DB_NAME=codedox"
        echo "      DB_USER=your-db-user"
        echo "      DB_PASSWORD=your-db-password"
        echo ""
        echo "   Note: For external DB, ensure the database is accessible from Docker containers"
        echo "   - If PostgreSQL is on host: use host.docker.internal"
        echo "   - If PostgreSQL is remote: use the actual hostname/IP"
    else
        echo "   Note: DB_HOST will be automatically overridden to 'postgres' for local Docker database"
    fi
    echo ""
    read -p "Press Enter after you've configured .env..."
else
    echo "✓ .env file exists"
    
    if [ "$USE_EXTERNAL_DB" = true ]; then
        echo "⚠️  Using external database - ensure DB_HOST, DB_PORT, DB_USER, DB_PASSWORD are set in .env"
    fi
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs

echo "🏗️  Building Docker images..."
echo "   This may take a few minutes on first run..."
docker-compose -f "$COMPOSE_FILE" build --no-cache

echo "🚀 Starting services..."
docker-compose -f "$COMPOSE_FILE" up -d

# Wait for PostgreSQL to be ready
if [ "$USE_EXTERNAL_DB" = true ]; then
    echo "⏳ Waiting for external PostgreSQL to be ready..."
    echo "   Note: Ensure your external PostgreSQL database is running and accessible"
    sleep 5
else
    echo "⏳ Waiting for PostgreSQL to be ready..."
    MAX_ATTEMPTS=30
    ATTEMPT=0
    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
            echo "✓ PostgreSQL is ready"
            break
        fi
        ATTEMPT=$((ATTEMPT + 1))
        if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
            echo "❌ PostgreSQL failed to start. Check logs with: docker-compose -f $COMPOSE_FILE logs postgres"
            exit 1
        fi
        sleep 2
    done
fi

# Initialize the database
echo "🗄️  Initializing database..."
docker-compose -f "$COMPOSE_FILE" exec -T api python cli.py init || {
    echo "⚠️  Database initialization failed. This might be normal if the database already exists."
    echo "   To reset the database, run: docker-compose -f $COMPOSE_FILE exec api python cli.py init --drop"
}

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ API is ready"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo "❌ API failed to start. Check logs with: docker-compose logs api"
        exit 1
    fi
    sleep 2
done

# Check if services are healthy
echo "🔍 Checking service health..."
docker-compose -f "$COMPOSE_FILE" ps

echo ""
echo "✅ Setup complete!"
echo ""
echo "📌 Access points:"
echo "   - Web UI: http://localhost:5173"
echo "   - API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"

if [ "$USE_EXTERNAL_DB" = true ]; then
    echo "   - PostgreSQL: External database (check your .env settings)"
else
    echo "   - PostgreSQL: localhost:5432 (user: postgres, password: postgres)"
fi

echo ""
echo "📚 Useful commands:"
echo "   - View container logs: docker-compose -f $COMPOSE_FILE logs -f"
if [ "$USE_EXTERNAL_DB" = true ]; then
    echo "   - View app logs: ./docker-logs.sh --external-db -f"
else
    echo "   - View app logs: ./docker-logs.sh -f"
fi
echo "   - Stop services: docker-compose -f $COMPOSE_FILE down"
if [ "$USE_EXTERNAL_DB" = true ]; then
    echo "   - Reset services: docker-compose -f $COMPOSE_FILE down && ./docker-setup.sh --external-db --clean"
else
    echo "   - Reset everything: docker-compose -f $COMPOSE_FILE down -v && ./docker-setup.sh --clean"
fi
echo "   - Run CLI command: docker-compose -f $COMPOSE_FILE exec api python cli.py <command>"
echo ""
echo "🎯 Next steps:"
echo "   1. Open http://localhost:5173 in your browser"
echo "   2. Start a crawl from the UI or run:"
echo "      docker-compose -f $COMPOSE_FILE exec api python cli.py crawl start 'Test' https://example.com --depth 0"
echo ""
