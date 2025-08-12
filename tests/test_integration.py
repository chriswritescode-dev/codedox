"""Integration tests for the CodeDox API."""

from uuid import uuid4


class TestEndToEndWorkflow:
    """Test complete workflows across multiple endpoints."""

    def test_crawl_and_search_workflow(self, client, mock_mcp_tools, sample_crawl_job,
                                     sample_document, sample_code_snippets):
        """Test creating a crawl job and searching its results."""
        # Step 1: Check initial statistics
        response = client.get("/api/statistics")
        assert response.status_code == 200
        initial_stats = response.json()
        assert initial_stats["total_sources"] == 1

        # Step 2: List sources
        response = client.get("/api/sources")
        assert response.status_code == 200
        data = response.json()
        sources = data["sources"]
        assert len(sources) == 1
        source_id = sources[0]["id"]

        # Step 3: Get specific source details
        response = client.get(f"/api/sources/{source_id}")
        assert response.status_code == 200
        source = response.json()
        assert source["snippets_count"] == 3

        # Step 4: Search for code snippets
        response = client.get("/api/search?language=python")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1

        # Step 5: Get specific snippet
        snippet_id = results[0]["snippet"]["id"]
        response = client.get(f"/api/snippets/{snippet_id}")
        assert response.status_code == 200
        snippet = response.json()
        assert snippet["language"] == "python"

    def test_mcp_workflow(self, client, mock_mcp_tools):
        """Test MCP tool workflow."""
        # Step 1: List available tools
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        tools = data["tools"]
        assert len(tools) == 3

        # Step 2: Execute init_crawl via MCP
        response = client.post(
            "/mcp/execute/init_crawl",
            json={
                "name": "MCP Test",
                "start_urls": ["https://mcp-test.com"],
                "max_depth": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "job_id" in data["result"]

        # Step 3: Search libraries via MCP
        response = client.post("/mcp/execute/search_libraries", json={"query": "test"})
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
        assert result["status"] == "success"
        assert "selected_library" in result
        library_id = result["selected_library"]["library_id"]

        # Step 4: Search via MCP
        response = client.post(
            "/mcp/execute/get_content",
            json={
                "library_id": library_id,
                "query": "test",
                "max_results": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert isinstance(data["result"], str)

    def test_streaming_workflow(self, client, mock_mcp_tools):
        """Test MCP streaming workflow."""
        # Step 1: Stream tools list
        response = client.post(
            "/mcp/stream",
            json={
                "method": "tools/list",
                "params": {}
            }
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Step 2: Stream tool execution
        response = client.post(
            "/mcp/stream",
            json={
                "method": "tools/execute",
                "params": {
                    "name": "search_libraries",
                    "params": {"query": "test"}
                }
            }
        )
        assert response.status_code == 200
        assert response.text.startswith("data: ")


class TestAPIConsistency:
    """Test API response consistency and data integrity."""

    def test_id_format_consistency(self, client, sample_crawl_job):
        """Test that IDs are consistently formatted as strings."""
        # Check in statistics
        response = client.get("/api/statistics")
        crawls = response.json()["recent_crawls"]
        if crawls:
            assert isinstance(crawls[0]["id"], str)

        # Check in sources
        response = client.get("/api/sources")
        data = response.json()
        sources = data["sources"]
        if sources:
            assert isinstance(sources[0]["id"], str)

        # Check in crawl jobs
        response = client.get("/api/crawl-jobs")
        jobs = response.json()
        if jobs:
            assert isinstance(jobs[0]["id"], str)

    def test_timestamp_format_consistency(self, client, sample_crawl_job):
        """Test that timestamps are consistently formatted."""
        response = client.get(f"/api/crawl-jobs/{sample_crawl_job.id}")
        job = response.json()

        # All timestamps should be ISO format strings
        assert job["created_at"].endswith("Z") or "+" in job["created_at"]
        if job["started_at"]:
            assert job["started_at"].endswith("Z") or "+" in job["started_at"]
        if job["completed_at"]:
            assert job["completed_at"].endswith("Z") or "+" in job["completed_at"]

    def test_error_response_format(self, client):
        """Test that error responses are consistently formatted."""
        # Test 404 errors
        fake_id = str(uuid4())
        endpoints = [
            f"/api/sources/{fake_id}",
            f"/api/crawl-jobs/{fake_id}",
            "/api/snippets/999999"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 404
            error = response.json()
            assert "detail" in error
            assert isinstance(error["detail"], str)
