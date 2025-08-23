#!/bin/bash
set -e

echo "🚀 CodeDox Docker Setup Script"
echo "=============================="

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

# Clean up any existing containers/volumes (optional)
if [ "$1" == "--clean" ]; then
    echo "🧹 Cleaning up existing Docker resources..."
    docker-compose down -v 2>/dev/null || true
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
    echo "⚠️  IMPORTANT: You need to add your LLM API key to the .env file!"
    echo "   1. Open .env in your editor"
    echo "   2. Replace 'your-api-key-here' with your actual API key:"
    echo "      - For OpenAI: Set CODE_LLM_API_KEY to your OpenAI API key"
    echo "      - For local LLMs: Also uncomment and set CODE_LLM_BASE_URL"
    echo ""
    echo "   Example for OpenAI:"
    echo "      CODE_LLM_API_KEY=sk-..."
    echo ""
    echo "   Example for local LLM (ollama, llama.cpp, lm studio)
    echo "      CODE_LLM_API_KEY=your-local-key"
    echo "      CODE_LLM_BASE_URL=http://host.docker.internal:1337/v1"
    echo ""
    echo "   Note: DB_HOST will be automatically overridden to 'postgres' for Docker"
    echo ""
    read -p "Press Enter after you've added your API key to .env..."
else
    echo "✓ .env file exists"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs

echo "🏗️  Building Docker images..."
echo "   This may take a few minutes on first run..."
docker-compose build --no-cache

echo "🚀 Starting services..."
docker-compose up -d

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo "❌ PostgreSQL failed to start. Check logs with: docker-compose logs postgres"
        exit 1
    fi
    sleep 2
done

# Initialize the database
echo "🗄️  Initializing database..."
docker-compose exec -T api python cli.py init || {
    echo "⚠️  Database initialization failed. This might be normal if the database already exists."
    echo "   To reset the database, run: docker-compose exec api python cli.py init --drop"
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
docker-compose ps

echo ""
echo "✅ Setup complete!"
echo ""
echo "📌 Access points:"
echo "   - Web UI: http://localhost:5173"
echo "   - API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - PostgreSQL: localhost:5432 (user: postgres, password: postgres)"
echo ""
echo "📚 Useful commands:"
echo "   - View logs: docker-compose logs -f"
echo "   - Stop services: docker-compose down"
echo "   - Reset everything: docker-compose down -v && ./docker-setup.sh --clean"
echo "   - Run CLI command: docker-compose exec api python cli.py <command>"
echo ""
echo "🎯 Next steps:"
echo "   1. Open http://localhost:5173 in your browser"
echo "   2. Start a crawl from the UI or run:"
echo "      docker-compose exec api python cli.py crawl start 'Test' https://example.com --depth 0"
echo ""
