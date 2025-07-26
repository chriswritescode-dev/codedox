# CodeDox Tests

This directory contains the test suite for the CodeDox API.

## Running Tests

### Basic Usage

```bash
# Run all tests
python cli.py test

# Run with coverage
python cli.py test --coverage

# Run with verbose output
python cli.py test --verbose

# Run only unit tests
python cli.py test --unit

# Run only integration tests
python cli.py test --integration

# Run tests matching a pattern
python cli.py test test_health
```

### Alternative: Using pytest directly

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src --cov-report=html tests/

# Run specific test file
pytest tests/test_api_routes.py

# Run specific test class
pytest tests/test_api_routes.py::TestHealthEndpoints

# Run specific test
pytest tests/test_api_routes.py::TestHealthEndpoints::test_health
```

## Test Structure

- `conftest.py` - Pytest configuration and fixtures
- `test_api_routes.py` - Tests for main API endpoints
- `test_mcp_routes.py` - Tests for MCP HTTP streaming endpoints
- `test_integration.py` - End-to-end integration tests

## Test Database

Tests use a separate PostgreSQL schema (`test_codedox`) in the same database to isolate test data from production data. This approach:
- Uses the same database but a different schema
- Automatically creates and drops the test schema
- Doesn't require additional database permissions
- Ensures tests run against real PostgreSQL features

The test schema is automatically created when tests run and dropped when they complete.

To use a different database for tests, set the individual database environment variables:
```bash
# Use TEST_DB_* variables for test-specific database
export TEST_DB_HOST="localhost"
export TEST_DB_PORT="5432"
export TEST_DB_NAME="test_db"
export TEST_DB_USER="postgres"
export TEST_DB_PASSWORD="postgres"

# Or the tests will fall back to the regular DB_* variables
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="codedox"
export DB_USER="postgres"
export DB_PASSWORD="postgres"

python cli.py test
```

## Fixtures

Key fixtures available:

- `client` - FastAPI test client
- `db` - Test database session
- `sample_crawl_job` - A completed crawl job
- `sample_document` - A document with content
- `sample_code_snippets` - Multiple code snippets
- `mock_mcp_tools` - Mocked MCP tools to avoid external calls

## Coverage

To view coverage report after running with `--coverage`:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Writing New Tests

1. Create test classes grouping related tests
2. Use descriptive test names starting with `test_`
3. Use fixtures to set up test data
4. Test both success and error cases
5. Mock external dependencies

Example:
```python
class TestNewFeature:
    def test_feature_success(self, client, sample_data):
        response = client.get("/api/new-feature")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
    
    def test_feature_not_found(self, client):
        response = client.get("/api/new-feature/999")
        assert response.status_code == 404
```