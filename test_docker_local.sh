#!/bin/bash
# Local automated test for Docker services

set -e

echo "🐋 CodeDox Docker Local Test"
echo "============================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to test a condition
test_check() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "Testing: $test_name... "
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local service_name="$1"
    local check_command="$2"
    local max_wait=30
    local waited=0
    
    echo -n "Waiting for $service_name"
    while ! eval "$check_command" > /dev/null 2>&1; do
        if [ $waited -ge $max_wait ]; then
            echo -e " ${RED}TIMEOUT${NC}"
            return 1
        fi
        echo -n "."
        sleep 2
        ((waited+=2))
    done
    echo -e " ${GREEN}READY${NC}"
    return 0
}

# Start tests
echo "1. Pre-flight checks"
echo "-------------------"
test_check "Docker installed" "docker --version"
test_check "Docker Compose installed" "docker-compose --version"
test_check "Docker daemon running" "docker ps"

echo ""
echo "2. Building and starting services"
echo "--------------------------------"

# Stop any existing services
echo "Cleaning up existing containers..."
docker-compose down > /dev/null 2>&1 || true

# Build images
echo "Building Docker images..."
if docker-compose build > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Build successful${NC}"
else
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi

# Start services
echo "Starting services..."
if docker-compose up -d > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Services started${NC}"
else
    echo -e "${RED}✗ Failed to start services${NC}"
    exit 1
fi

echo ""
echo "3. Service health checks"
echo "-----------------------"

# Wait for PostgreSQL
wait_for_service "PostgreSQL" "docker exec codedox_postgres pg_isready -U postgres"

# Wait for API
wait_for_service "API Server" "curl -s -f http://localhost:8000/health"

# Wait for Frontend
wait_for_service "Frontend" "curl -s -f http://localhost:5173"

echo ""
echo "4. Functional tests"
echo "------------------"

# Test database connection
test_check "Database accessible" "docker exec codedox_postgres psql -U postgres -d codedox -c 'SELECT 1'"

# Test API endpoints
test_check "API health endpoint" "curl -s -f http://localhost:8000/health"
test_check "MCP tools endpoint" "curl -s -f http://localhost:8000/mcp/tools"
test_check "API docs available" "curl -s -f http://localhost:8000/docs"

# Test API functionality
test_check "Search endpoint responds" "curl -s -f -X POST http://localhost:8000/search -H 'Content-Type: application/json' -d '{\"query\":\"test\",\"limit\":1}'"

# Test frontend
test_check "Frontend loads" "curl -s http://localhost:5173 | grep -q '<title>'"

echo ""
echo "5. Container status"
echo "------------------"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep codedox || true

echo ""
echo "============================"
echo "Test Results:"
echo -e "  Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "  Failed: ${RED}$TESTS_FAILED${NC}"
echo "============================"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "Services are running at:"
    echo "  • Frontend: http://localhost:5173"
    echo "  • API: http://localhost:8000"
    echo "  • API Docs: http://localhost:8000/docs"
    echo ""
    echo "To stop services: docker-compose down"
    exit 0
else
    echo -e "\n${RED}❌ Some tests failed${NC}"
    echo ""
    echo "Check logs with:"
    echo "  • docker-compose logs"
    echo "  • docker logs codedox_api"
    echo "  • docker logs codedox_postgres"
    
    # Show recent logs for debugging
    echo ""
    echo "Recent API logs:"
    docker logs --tail 10 codedox_api 2>&1 || true
    
    exit 1
fi