#!/bin/bash
set -e

echo "📋 CodeDox Docker Logs Viewer"
echo "=============================="

COMPOSE_FILE="docker-compose.yml"

# Parse arguments
FOLLOW=false
TAIL_LINES=100

while [[ $# -gt 0 ]]; do
    case $1 in
        --external-db)
            COMPOSE_FILE="docker-compose.external-db.yml"
            shift
            ;;
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            TAIL_LINES="$2"
            shift 2
            ;;
        --help)
            echo "View CodeDox application logs from Docker volume"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --external-db    Use external database compose file"
            echo "  -f, --follow     Follow log output (like tail -f)"
            echo "  -n, --lines N    Number of lines to show (default: 100)"
            echo "  --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Show last 100 lines"
            echo "  $0 -f                 # Follow logs in real-time"
            echo "  $0 -n 500             # Show last 500 lines"
            echo "  $0 --external-db -f   # Follow logs with external DB setup"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Check if container is running
if ! docker-compose -f "$COMPOSE_FILE" ps api | grep -q "Up"; then
    echo "❌ CodeDox API container is not running."
    echo "   Start it with: docker-compose -f $COMPOSE_FILE up -d"
    exit 1
fi

echo "Using compose file: $COMPOSE_FILE"
echo ""

if [ "$FOLLOW" = true ]; then
    echo "Following logs (Ctrl+C to stop)..."
    echo "=================================="
    docker-compose -f "$COMPOSE_FILE" exec api tail -f /app/logs/codedox.log
else
    echo "Showing last $TAIL_LINES lines..."
    echo "=================================="
    docker-compose -f "$COMPOSE_FILE" exec api tail -n "$TAIL_LINES" /app/logs/codedox.log
fi
