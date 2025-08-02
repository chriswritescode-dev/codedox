#!/bin/bash
# Test Docker services health for CodeDox

set -e

echo "🐋 Testing CodeDox Docker Services"
echo "=================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a container is healthy
check_container() {
    local container=$1
    local name=$2
    
    echo -n "Checking $name... "
    
    # Check if container is running
    if docker ps --format "table {{.Names}}" | grep -q "^${container}$"; then
        # Check health status if available
        health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $container 2>/dev/null || echo "none")
        
        if [ "$health" = "healthy" ]; then
            echo -e "${GREEN}✓ Healthy${NC}"
            return 0
        elif [ "$health" = "none" ] || [ -z "$health" ]; then
            # No health check, just check if running
            running=$(docker inspect --format='{{.State.Running}}' $container 2>/dev/null || echo "false")
            if [ "$running" = "true" ]; then
                echo -e "${GREEN}✓ Running${NC}"
                return 0
            else
                echo -e "${RED}✗ Not running${NC}"
                return 1
            fi
        else
            echo -e "${YELLOW}⚠ Status: $health${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ Not running${NC}"
        return 1
    fi
}

# Function to check HTTP endpoint
check_endpoint() {
    local url=$1
    local name=$2
    local max_attempts=15
    local attempt=0
    
    echo -n "Checking $name... "
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f -o /dev/null "$url"; then
            echo -e "${GREEN}✓ Responding${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo -e "${RED}✗ Not responding after $((max_attempts * 2)) seconds${NC}"
    return 1
}

# Function to check PostgreSQL
check_postgres() {
    local max_attempts=15
    local attempt=0
    
    echo -n "Checking PostgreSQL... "
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec codedox-postgres pg_isready -U postgres > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Ready${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo -e "${RED}✗ Not ready after $((max_attempts * 2)) seconds${NC}"
    return 1
}

# Main test sequence
main() {
    local all_passed=true
    
    # 1. Check if Docker is running
    echo "1. Checking Docker..."
    if ! docker version > /dev/null 2>&1; then
        echo -e "${RED}✗ Docker is not running${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker is running${NC}"
    
    # 2. Check if services are up
    echo -e "\n2. Checking containers..."
    
    check_container "codedox-postgres" "PostgreSQL container" || all_passed=false
    check_container "codedox-api" "API container" || all_passed=false
    check_container "codedox-frontend" "Frontend container" || all_passed=false
    
    # 3. Check database
    echo -e "\n3. Checking database..."
    check_postgres || all_passed=false
    
    # 4. Check service endpoints
    echo -e "\n4. Checking service endpoints..."
    
    check_endpoint "http://localhost:8000/api/health" "API health" || all_passed=false
    check_endpoint "http://localhost:8000/mcp/tools" "MCP tools" || all_passed=false
    check_endpoint "http://localhost:5173" "Frontend" || all_passed=false
    
    # 5. Quick functional test
    echo -e "\n5. Running functional tests..."
    echo -n "Testing API search... "
    
    if curl -s "http://localhost:8000/api/search?query=test&limit=1" \
        -o /dev/null -w "%{http_code}" | grep -q "200"; then
        echo -e "${GREEN}✓ Working${NC}"
    else
        echo -e "${RED}✗ Failed${NC}"
        all_passed=false
    fi
    
    # Summary
    echo -e "\n=================================="
    if [ "$all_passed" = true ]; then
        echo -e "${GREEN}✅ All services are healthy!${NC}"
        echo -e "\nAccess points:"
        echo "  • Frontend: http://localhost:5173"
        echo "  • API: http://localhost:8000"
        echo "  • API Docs: http://localhost:8000/docs"
        echo "  • MCP Tools: http://localhost:8000/mcp/tools"
        exit 0
    else
        echo -e "${RED}❌ Some services failed health checks${NC}"
        echo -e "\nTroubleshooting:"
        echo "  • View logs: docker-compose logs"
        echo "  • Check specific service: docker logs codedox-api"
        echo "  • Restart services: docker-compose restart"
        exit 1
    fi
}

# Run main function
main