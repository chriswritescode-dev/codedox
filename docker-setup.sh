#!/bin/bash
set -e

echo "🚀 CodeDox Docker Setup Script"
echo "=============================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your LLM API key!"
    echo "   Set CODE_LLM_API_KEY to your actual key"
    echo "   For local LLMs (Jan, Ollama), also set CODE_LLM_BASE_URL"
    echo ""
    read -p "Press Enter to continue after adding your API key..."
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "🏗️  Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

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
echo "   - Reset everything: docker-compose down -v"
echo "   - Run CLI command: docker-compose exec api python cli.py <command>"
echo ""
echo "🎯 Next steps:"
echo "   1. Open http://localhost:5173 in your browser"
echo "   2. Start a crawl from the UI or run:"
echo "      docker-compose exec api python cli.py crawl 'Test' https://example.com --depth 0"
echo ""