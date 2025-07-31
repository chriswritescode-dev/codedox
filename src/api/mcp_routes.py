"""MCP HTTP streaming routes for FastAPI."""

import json
import logging
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Body, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..mcp_server.server import MCPServer
from .auth import verify_mcp_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp")

# Initialize MCP server
mcp_server = MCPServer()


class MCPRequest(BaseModel):
    """MCP request format."""
    method: str
    params: Dict[str, Any] = {}


class MCPToolDefinition(BaseModel):
    """MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]


async def stream_response(data: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """Stream a JSON response with Server-Sent Events format."""
    # Send the response as a single SSE event
    yield f"data: {json.dumps(data)}\n\n"


@router.get("/health")
async def mcp_health() -> Dict[str, str]:
    """Check MCP service health."""
    return {"status": "healthy", "service": "mcp-http"}


@router.get("/tools", dependencies=[Depends(verify_mcp_token)])
async def list_tools() -> Dict[str, Any]:
    """List available MCP tools."""
    return {"tools": mcp_server.get_tool_definitions()}


@router.post("/execute/{tool_name}", dependencies=[Depends(verify_mcp_token)])
async def execute_tool(tool_name: str, request: Request) -> Dict[str, Any]:
    """Execute a specific MCP tool."""
    try:
        # Get params from request body
        try:
            params = await request.json()
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON: {str(e)}")
        
        # Get tool definitions to validate required parameters
        tool_defs = {tool["name"]: tool for tool in mcp_server.get_tool_definitions()}
        
        if tool_name not in tool_defs:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
        
        # Validate required parameters
        tool_def = tool_defs[tool_name]
        required_params = tool_def["input_schema"].get("required", [])
        for param in required_params:
            if param not in params:
                raise HTTPException(status_code=422, detail=f"Missing required parameter: {param}")
        
        # Execute the tool
        result = await mcp_server.execute_tool(tool_name, params)
        
        # Format result based on tool type
        if tool_name == "get_content" and isinstance(result, str):
            return {"result": result, "format": "text"}
        else:
            return {"result": result}
        
    except ValueError as e:
        # Handle unknown tool errors from execute_tool
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream/execute/{tool_name}", dependencies=[Depends(verify_mcp_token)])
async def execute_tool_stream(tool_name: str, request: Request) -> StreamingResponse:
    """Execute a tool and stream the response."""
    try:
        # Get params from request body
        try:
            params = await request.json()
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON: {str(e)}")
        
        # Get tool definitions to validate
        tool_defs = {tool["name"]: tool for tool in mcp_server.get_tool_definitions()}
        
        if tool_name not in tool_defs:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        # Validate required parameters
        tool_def = tool_defs[tool_name]
        required_params = tool_def["input_schema"].get("required", [])
        for param in required_params:
            if param not in params:
                raise ValueError(f"Missing required parameter: {param}")
        
        # Execute the tool
        result = await mcp_server.execute_tool(tool_name, params)
        
        # Stream the response
        return StreamingResponse(
            stream_response({"tool": tool_name, "result": result}),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable Nginx buffering
            }
        )
        
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        error_response = {"error": str(e), "tool": tool_name}
        return StreamingResponse(
            stream_response(error_response),
            media_type="text/event-stream",
            status_code=500
        )


@router.post("/stream", dependencies=[Depends(verify_mcp_token)])
async def mcp_stream(request: Request) -> StreamingResponse:
    """
    MCP streaming endpoint that handles multiple request types.
    Compatible with LLM tools that expect streaming responses.
    """
    # Parse request body
    try:
        body = await request.json()
        mcp_request = MCPRequest(**body)
    except Exception as e:
        return StreamingResponse(
            stream_response({"error": f"Invalid request format: {str(e)}"}),
            media_type="text/event-stream",
            status_code=400
        )
    
    method = mcp_request.method
    params = mcp_request.params
    
    try:
        if method == "initialize":
            # Handle MCP initialization
            response_data = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "sampling": {}
                },
                "serverInfo": {
                    "name": "codedox-mcp",
                    "version": "1.0.1"
                }
            }
            
        elif method == "tools/list":
            # Get tools from MCP server and convert to protocol format
            tool_defs = mcp_server.get_tool_definitions()
            tools = [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": tool["input_schema"]
                }
                for tool in tool_defs
            ]
            response_data = {"tools": tools}
            
        elif method == "tools/call":
            # Execute a tool (MCP protocol uses tools/call)
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if not tool_name:
                raise ValueError("Tool name is required")
            
            # Execute the tool using MCP server
            result = await mcp_server.execute_tool(tool_name, tool_args)
            
            # Format response according to MCP protocol
            response_data = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result) if isinstance(result, dict) else str(result)
                    }
                ]
            }
            
        elif method == "tools/execute":
            # Legacy support for tools/execute
            tool_name = params.get("name")
            tool_params = params.get("params", {})
            
            if not tool_name:
                raise ValueError("Tool name is required")
            
            # Execute the tool using MCP server
            result = await mcp_server.execute_tool(tool_name, tool_params)
            
            response_data = {
                "method": method,
                "tool": tool_name,
                "result": result
            }
            
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Stream the response
        return StreamingResponse(
            stream_response(response_data),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in MCP stream: {e}")
        error_response = {"method": method, "error": str(e)}
        return StreamingResponse(
            stream_response(error_response),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )