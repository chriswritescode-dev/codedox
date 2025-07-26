#!/bin/bash
# Comprehensive Docker test runner for CodeDox

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TEST_MODE=${1:-"full"}  # full, quick, or health
CLEANUP=${CLEANUP:-"true"}

echo -e "${BLUE}🐋 CodeDox Docker Test Suite${NC}"
echo "=============================="
echo "Mode: $TEST_MODE"
echo ""

# Function to cleanup
cleanup() {
    if [ "$CLEANUP" = "true" ]; then
        echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
        docker-compose down -v 2>/dev/null || true
        docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Function to run tests
run_tests() {
    local test_type=$1
    
    case $test_type in
        "quick")
            echo -e "${BLUE}Running quick health checks...${NC}\n"
            
            # Start services
            echo "1. Starting services..."
            docker-compose up -d
            
            # Wait for services
            echo -e "\n2. Waiting for services to be ready..."
            sleep 10
            
            # Run health check
            echo -e "\n3. Running health checks..."
            ./test_docker_health.sh
            ;;
            
        "health")
            echo -e "${BLUE}Running service health tests...${NC}\n"
            
            # Build if needed
            echo "1. Building Docker images..."
            docker-compose build
            
            # Start services
            echo -e "\n2. Starting services..."
            docker-compose up -d
            
            # Run health check
            echo -e "\n3. Running health checks..."
            sleep 15  # Give more time for services to start
            ./test_docker_health.sh
            
            # Show logs if failed
            if [ $? -ne 0 ]; then
                echo -e "\n${RED}Health checks failed. Showing logs:${NC}"
                docker-compose logs --tail=50
            fi
            ;;
            
        "full")
            echo -e "${BLUE}Running full test suite...${NC}\n"
            
            # 1. Build images
            echo "1. Building Docker images..."
            docker-compose build
            if [ $? -ne 0 ]; then
                echo -e "${RED}✗ Build failed${NC}"
                exit 1
            fi
            echo -e "${GREEN}✓ Images built successfully${NC}\n"
            
            # 2. Start main services
            echo "2. Starting main services..."
            docker-compose up -d postgres api
            sleep 10
            
            # 3. Initialize database
            echo -e "\n3. Initializing database..."
            docker-compose exec -T api python cli.py init --drop
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Database initialized${NC}"
            else
                echo -e "${RED}✗ Database initialization failed${NC}"
                exit 1
            fi
            
            # 4. Start frontend
            echo -e "\n4. Starting frontend..."
            docker-compose up -d frontend
            
            # 5. Run health checks
            echo -e "\n5. Running health checks..."
            sleep 10
            ./test_docker_health.sh
            if [ $? -ne 0 ]; then
                echo -e "${RED}✗ Health checks failed${NC}"
                exit 1
            fi
            
            # 6. Run integration tests
            echo -e "\n6. Running integration tests..."
            docker-compose -f docker-compose.test.yml run --rm test
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Integration tests passed${NC}"
            else
                echo -e "${RED}✗ Integration tests failed${NC}"
                exit 1
            fi
            
            # 7. Test MCP functionality
            echo -e "\n7. Testing MCP functionality..."
            echo -n "  - Listing tools: "
            if curl -s http://localhost:8000/mcp/tools | grep -q "search_libraries"; then
                echo -e "${GREEN}✓${NC}"
            else
                echo -e "${RED}✗${NC}"
                exit 1
            fi
            
            echo -n "  - Testing search: "
            response=$(curl -s -X POST http://localhost:8000/mcp/execute/search_libraries \
                -H "Content-Type: application/json" \
                -d '{"query": "test"}')
            if echo "$response" | grep -q "libraries"; then
                echo -e "${GREEN}✓${NC}"
            else
                echo -e "${RED}✗${NC}"
                exit 1
            fi
            
            echo -e "${GREEN}✓ All MCP tests passed${NC}"
            ;;
            
        *)
            echo -e "${RED}Unknown test mode: $test_type${NC}"
            echo "Usage: $0 [quick|health|full]"
            exit 1
            ;;
    esac
}

# Main execution
main() {
    # Check prerequisites
    echo "Checking prerequisites..."
    
    # Check Docker
    if ! docker version > /dev/null 2>&1; then
        echo -e "${RED}✗ Docker is not installed or not running${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker is running${NC}"
    
    # Check docker-compose
    if ! docker-compose version > /dev/null 2>&1; then
        echo -e "${RED}✗ docker-compose is not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ docker-compose is available${NC}"
    
    # Check .env file
    if [ ! -f .env ]; then
        echo -e "${YELLOW}⚠ .env file not found, using defaults${NC}"
        cp .env.example .env
    fi
    
    echo ""
    
    # Run tests
    run_tests $TEST_MODE
    
    # Summary
    echo -e "\n${GREEN}=============================="
    echo -e "✅ Docker tests completed successfully!${NC}"
    echo -e "==============================\n"
    
    if [ "$TEST_MODE" = "full" ] && [ "$CLEANUP" = "false" ]; then
        echo "Services are still running. You can:"
        echo "  • View the frontend at http://localhost:5173"
        echo "  • Access the API at http://localhost:8000"
        echo "  • Stop services with: docker-compose down"
    fi
}

# Run main
main