"""Tests for MCP Streamable HTTP Transport."""

import json
import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def parse_sse_response(content: str) -> dict:
    """Parse SSE response to extract JSON data."""
    lines = content.strip().split('\n')
    for line in lines:
        if line.startswith('data: {'):
            return json.loads(line[6:])  # Remove 'data: ' prefix
    raise ValueError("No JSON data found in SSE stream")


def test_mcp_streamable_initialize_json(client):
    """Test MCP initialization via streamable transport with JSON response."""
    init_request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    # Request JSON response by putting application/json first
    response = client.post(
        "/mcp",
        json=init_request,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "1"
    assert "result" in result
    assert "protocolVersion" in result["result"]
    assert "serverInfo" in result["result"]


def test_mcp_streamable_initialize_sse(client):
    """Test MCP initialization via streamable transport with SSE response."""
    init_request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.1"
            }
        }
    }
    
    # Request SSE response by putting text/event-stream first
    response = client.post(
        "/mcp",
        json=init_request,
        headers={
            "Accept": "text/event-stream, application/json",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    
    # Parse SSE response
    content = response.content.decode()
    result = parse_sse_response(content)
    
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "1"
    assert "result" in result
    assert "protocolVersion" in result["result"]
    assert "serverInfo" in result["result"]


def test_mcp_streamable_tools_list_json(client):
    """Test listing tools via streamable transport with JSON response."""
    tools_request = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/list",
        "params": {}
    }
    
    response = client.post(
        "/mcp",
        json=tools_request,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "2"
    assert "result" in result
    assert "tools" in result["result"]
    
    tools = result["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]
    
    assert "init_crawl" in tool_names
    assert "search_libraries" in tool_names
    assert "get_content" in tool_names


def test_mcp_streamable_tools_list_sse(client):
    """Test listing tools via streamable transport with SSE response."""
    tools_request = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/list",
        "params": {}
    }
    
    response = client.post(
        "/mcp",
        json=tools_request,
        headers={
            "Accept": "text/event-stream, application/json",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    
    # Parse SSE response
    content = response.content.decode()
    result = parse_sse_response(content)
    
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "2"
    assert "result" in result
    assert "tools" in result["result"]
    
    tools = result["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]
    
    assert "init_crawl" in tool_names
    assert "search_libraries" in tool_names
    assert "get_content" in tool_names


def test_mcp_streamable_batch_request_json(client):
    """Test batch requests via streamable transport with JSON response."""
    batch_request = [
        {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        },
        {
            "jsonrpc": "2.0",
            "id": "2",
            "method": "tools/list",
            "params": {}
        }
    ]
    
    response = client.post(
        "/mcp",
        json=batch_request,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")
    
    results = response.json()
    assert len(results) == 2
    assert all(result["jsonrpc"] == "2.0" for result in results)
    assert results[0]["id"] == "1"
    assert results[1]["id"] == "2"


def test_mcp_streamable_batch_request_sse(client):
    """Test batch requests via streamable transport with SSE response."""
    batch_request = [
        {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        },
        {
            "jsonrpc": "2.0",
            "id": "2",
            "method": "tools/list",
            "params": {}
        }
    ]
    
    response = client.post(
        "/mcp",
        json=batch_request,
        headers={
            "Accept": "text/event-stream, application/json",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    
    # Parse SSE response - should contain multiple events
    content = response.content.decode()
    lines = content.strip().split('\n')
    
    results = []
    for line in lines:
        if line.startswith('data: {'):
            results.append(json.loads(line[6:]))
    
    assert len(results) == 2
    assert all(result["jsonrpc"] == "2.0" for result in results)
    assert results[0]["id"] == "1"
    assert results[1]["id"] == "2"


def test_mcp_streamable_invalid_accept_header(client):
    """Test that invalid Accept header is rejected."""
    init_request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize",
        "params": {}
    }
    
    response = client.post(
        "/mcp",
        json=init_request,
        headers={
            "Accept": "application/json",  # Missing text/event-stream
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 406


def test_mcp_streamable_invalid_json(client):
    """Test that invalid JSON is rejected."""
    response = client.post(
        "/mcp",
        data="invalid json",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 400


def test_mcp_streamable_notification(client):
    """Test notifications (no response expected)."""
    notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {}
    }
    
    response = client.post(
        "/mcp",
        json=notification,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    
    # Notifications should return 202 Accepted with no content
    assert response.status_code == 202


def test_mcp_streamable_unknown_method(client):
    """Test error handling for unknown methods."""
    unknown_request = {
        "jsonrpc": "2.0",
        "id": "3",
        "method": "unknown/method",
        "params": {}
    }
    
    response = client.post(
        "/mcp",
        json=unknown_request,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "3"
    assert "error" in result
    assert result["error"]["code"] == -32601
    assert "not found" in result["error"]["message"].lower()


def test_mcp_streamable_session_handling(client):
    """Test session ID handling."""
    init_request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    
    response = client.post(
        "/mcp",
        json=init_request,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Mcp-Session-Id": "test-session-123"
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "1"
    assert "result" in result


def test_mcp_streamable_prefixed_tool_name(client):
    """Test handling of prefixed tool names (e.g., vszd2c_search_libraries)."""
    # First initialize
    init_request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    
    response = client.post(
        "/mcp",
        json=init_request,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    
    # Now test prefixed tool call
    tool_request = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/call",
        "params": {
            "name": "vszd2c_search_libraries",  # Prefixed tool name
            "arguments": {
                "query": "react",
                "max_results": 5
            }
        }
    }
    
    response = client.post(
        "/mcp",
        json=tool_request,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == "2"
    
    # Should have result (tool extracted correctly) or error with details
    assert "result" in result or "error" in result
    
    # If error, it should have meaningful details
    if "error" in result:
        assert "message" in result["error"]
        assert result["error"]["message"] != "{}"  # Should not be empty