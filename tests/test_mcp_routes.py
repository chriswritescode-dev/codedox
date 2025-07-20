"""Tests for MCP HTTP streaming routes."""

import json
import pytest
from uuid import uuid4


class TestMCPHealthEndpoint:
    """Test MCP health endpoint."""
    
    def test_mcp_health(self, client):
        """Test MCP health check."""
        response = client.get("/mcp/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "mcp-http"


class TestMCPToolsEndpoint:
    """Test MCP tools listing."""
    
    def test_list_tools(self, client):
        """Test listing available MCP tools."""
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        tools = data["tools"]
        
        assert len(tools) == 4
        tool_names = [tool["name"] for tool in tools]
        assert "init_crawl" in tool_names
        assert "search_libraries" in tool_names
        assert "get_content" in tool_names
        assert "get_snippet_details" in tool_names
        
        # Check tool structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
            assert "properties" in tool["input_schema"]


class TestMCPExecuteEndpoints:
    """Test MCP tool execution endpoints."""
    
    def test_execute_init_crawl(self, client, mock_mcp_tools):
        """Test executing init_crawl tool."""
        response = client.post(
            "/mcp/execute/init_crawl",
            json={
                "name": "Test Docs",
                "start_urls": ["https://test.com"],
                "max_depth": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
        assert result["status"] == "started"
        assert "job_id" in result
    
    def test_execute_search_libraries(self, client, mock_mcp_tools):
        """Test executing search_libraries tool."""
        response = client.post("/mcp/execute/search_libraries", json={"query": "test"})
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
        assert result["status"] == "success"
        assert "selected_library" in result
        assert result["selected_library"]["name"] == "Test Source"
    
    def test_execute_get_content(self, client, mock_mcp_tools):
        """Test executing get_content tool."""
        response = client.post(
            "/mcp/execute/get_content",
            json={
                "library_id": "test-lib-id",
                "query": "authentication",
                "max_results": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
        assert isinstance(result, str)
        assert "Found 1 results" in result
    
    def test_execute_get_content_without_library_id(self, client, mock_mcp_tools):
        """Test executing get_content tool without required library_id."""
        response = client.post(
            "/mcp/execute/get_content",
            json={
                "query": "authentication",
                "max_results": 5
            }
        )
        assert response.status_code == 422
        data = response.json()
        assert "Missing required parameter: library_id" in data["detail"]
    
    def test_execute_get_content_without_query(self, client, mock_mcp_tools):
        """Test executing get_content tool without optional query param - should succeed."""
        response = client.post(
            "/mcp/execute/get_content",
            json={
                "library_id": "test-lib-id",
                "max_results": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
    
    def test_execute_get_content_with_library_name(self, client, mock_mcp_tools):
        """Test executing get_content tool with library name instead of ID."""
        response = client.post(
            "/mcp/execute/get_content",
            json={
                "library_id": "nextjs",  # Using name instead of UUID
                "query": "routing",
                "max_results": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
        # The mock should handle this gracefully
        assert isinstance(result, str)
    
    def test_execute_get_snippet_details(self, client, mock_mcp_tools):
        """Test executing get_snippet_details tool."""
        response = client.post(
            "/mcp/execute/get_snippet_details",
            json={
                "snippet_id": 123
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
        assert result["id"] == 123
        assert result["title"] == "Test Snippet"
        assert result["language"] == "python"
        assert "document" in result
        assert result["document"]["title"] == "Test Document"
    
    def test_execute_get_snippet_details_not_found(self, client, mock_mcp_tools):
        """Test executing get_snippet_details tool with non-existent ID."""
        response = client.post(
            "/mcp/execute/get_snippet_details",
            json={
                "snippet_id": 999
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        result = data["result"]
        assert "error" in result
        assert result["error"] == "Snippet not found"
        assert result["snippet_id"] == 999
    
    def test_execute_get_snippet_details_missing_id(self, client, mock_mcp_tools):
        """Test executing get_snippet_details tool without required snippet_id param."""
        response = client.post(
            "/mcp/execute/get_snippet_details",
            json={}
        )
        assert response.status_code == 422
        data = response.json()
        assert "Missing required parameter: snippet_id" in data["detail"]
    
    def test_execute_invalid_tool(self, client):
        """Test executing non-existent tool."""
        response = client.post(
            "/mcp/execute/invalid_tool",
            json={"param": "value"}
        )
        assert response.status_code == 404
        # Due to the global 404 handler, we get a generic message
        assert response.json()["detail"] == "Resource not found"
    
    def test_execute_missing_params(self, client, mock_mcp_tools):
        """Test executing tool with missing required params."""
        response = client.post(
            "/mcp/execute/init_crawl",
            json={"name": "Test"}  # Missing start_urls
        )
        assert response.status_code == 422  # FastAPI validation error


class TestMCPStreamEndpoints:
    """Test MCP streaming endpoints."""
    
    def test_stream_request(self, client, mock_mcp_tools):
        """Test MCP stream endpoint."""
        response = client.post(
            "/mcp/stream",
            json={
                "method": "tools/list",
                "params": {}
            }
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Parse SSE response
        content = response.text
        assert content.startswith("data: ")
        json_data = json.loads(content[6:].strip())  # Remove "data: " prefix
        assert "tools" in json_data
        assert isinstance(json_data["tools"], list)
        assert len(json_data["tools"]) == 4  # init_crawl, search_libraries, get_content, get_snippet_details
    
    def test_stream_execute_tool(self, client, mock_mcp_tools):
        """Test streaming tool execution."""
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
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Parse SSE response
        content = response.text
        assert content.startswith("data: ")
        json_data = json.loads(content[6:].strip())
        assert "result" in json_data
        assert isinstance(json_data["result"], dict)
    
    def test_stream_invalid_method(self, client):
        """Test stream with invalid method."""
        response = client.post(
            "/mcp/stream",
            json={
                "method": "invalid/method",
                "params": {}
            }
        )
        assert response.status_code == 200  # Still returns 200 with error in stream
        content = response.text
        assert content.startswith("data: ")
        json_data = json.loads(content[6:].strip())
        assert "error" in json_data
    
    def test_stream_execute_specific_tool(self, client, mock_mcp_tools):
        """Test stream execute endpoint for specific tool."""
        response = client.post(
            "/mcp/stream/execute/get_content",
            json={
                "library_id": "test-lib-id",
                "query": "test query",
                "max_results": 3
            }
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        content = response.text
        assert content.startswith("data: ")
        json_data = json.loads(content[6:].strip())
        assert "result" in json_data
        assert "tool" in json_data
        assert json_data["tool"] == "get_content"
        assert isinstance(json_data["result"], str)


class TestMCPErrorHandling:
    """Test MCP error handling."""
    
    def test_malformed_json(self, client):
        """Test handling of malformed JSON."""
        response = client.post(
            "/mcp/execute/init_crawl",
            content="invalid json",
            headers={"content-type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_tool_execution_error(self, client, monkeypatch):
        """Test handling of tool execution errors."""
        async def mock_failing_tool(*args, **kwargs):
            raise Exception("Tool execution failed")
        
        from src.mcp_server.tools import MCPTools
        monkeypatch.setattr(MCPTools, "init_crawl", mock_failing_tool)
        
        response = client.post(
            "/mcp/execute/init_crawl",
            json={
                "name": "Test",
                "start_urls": ["https://test.com"]
            }
        )
        # Check that we get an error response
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert "Tool execution failed" in detail