"""MCP HTTP streaming routes for FastAPI."""

import json
import logging
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..mcp_server.tools import MCPTools

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp")

# Initialize MCP tools
mcp_tools = MCPTools()


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
async def mcp_health():
    """Check MCP service health."""
    return {"status": "healthy", "service": "mcp-http"}


@router.get("/tools")
async def list_tools():
    """List available MCP tools."""
    tools = [
        {
            "name": "init_crawl",
            "description": "Initialize a new web crawl job for documentation",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Library/framework name (e.g., 'Next.js', '.NET')"
                    },
                    "start_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "URLs to start crawling from"
                    },
                    "max_depth": {
                        "type": "integer",
                        "default": 1,
                        "minimum": 0,
                        "maximum": 3,
                        "description": "Maximum crawl depth (0-3)"
                    },
                    "domain_filter": {
                        "type": "string",
                        "description": "Optional domain restriction pattern"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata (repository, description, etc.)"
                    }
                },
                "required": ["name", "start_urls"]
            }
        },
        {
            "name": "get_sources",
            "description": "Get list of available libraries/sources with stats",
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Optional specific job ID to filter by"
                    }
                }
            }
        },
        {
            "name": "search_content",
            "description": "Search code snippets across all sources or in a specific library",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for content"
                    },
                    "source": {
                        "type": "string",
                        "description": "Optional library name filter (e.g., 'Next.js', '.NET')"
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional programming language filter"
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                        "description": "Maximum results to return"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_snippet_details",
            "description": "Get detailed information about a specific code snippet by ID",
            "input_schema": {
                "type": "object",
                "properties": {
                    "snippet_id": {
                        "type": "integer",
                        "description": "The ID of the snippet (from search results)"
                    }
                },
                "required": ["snippet_id"]
            }
        }
    ]
    
    return {"tools": tools}


@router.post("/execute/{tool_name}")
async def execute_tool(tool_name: str, params: Dict[str, Any]):
    """Execute a specific MCP tool."""
    try:
        if tool_name == "init_crawl":
            # Validate required params
            if "name" not in params:
                raise HTTPException(status_code=422, detail="Missing required parameter: name")
            if "start_urls" not in params:
                raise HTTPException(status_code=422, detail="Missing required parameter: start_urls")
                
            result = await mcp_tools.init_crawl(
                name=params["name"],
                start_urls=params["start_urls"],
                max_depth=params.get("max_depth", 1),
                domain_filter=params.get("domain_filter"),
                metadata=params.get("metadata", {})
            )
            
        elif tool_name == "get_sources":
            result = await mcp_tools.get_sources(
                job_id=params.get("job_id")
            )
            
        elif tool_name == "search_content":
            # Validate required param
            if "query" not in params:
                raise HTTPException(status_code=422, detail="Missing required parameter: query")
                
            result = await mcp_tools.search_content(
                query=params["query"],
                source=params.get("source"),
                language=params.get("language"),
                max_results=params.get("max_results", 10)
            )
            
        elif tool_name == "get_snippet_details":
            # Validate required param
            if "snippet_id" not in params:
                raise HTTPException(status_code=422, detail="Missing required parameter: snippet_id")
                
            result = await mcp_tools.get_snippet_details(
                snippet_id=params["snippet_id"]
            )
            
        else:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
        
        return {"result": result}
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream/execute/{tool_name}")
async def execute_tool_stream(tool_name: str, params: Dict[str, Any]):
    """Execute a tool and stream the response."""
    try:
        # Execute the tool
        if tool_name == "init_crawl":
            result = await mcp_tools.init_crawl(
                name=params["name"],
                start_urls=params["start_urls"],
                max_depth=params.get("max_depth", 1),
                domain_filter=params.get("domain_filter"),
                metadata=params.get("metadata", {})
            )
            
        elif tool_name == "get_sources":
            result = await mcp_tools.get_sources(
                job_id=params.get("job_id")
            )
            
        elif tool_name == "search_content":
            # Validate required param
            if "query" not in params:
                raise HTTPException(status_code=422, detail="Missing required parameter: query")
                
            result = await mcp_tools.search_content(
                query=params["query"],
                source=params.get("source"),
                language=params.get("language"),
                max_results=params.get("max_results", 10)
            )
            
        elif tool_name == "get_snippet_details":
            # Validate required param
            if "snippet_id" not in params:
                raise HTTPException(status_code=422, detail="Missing required parameter: snippet_id")
                
            result = await mcp_tools.get_snippet_details(
                snippet_id=params["snippet_id"]
            )
            
        else:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
        
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


@router.post("/stream")
async def mcp_stream(request: MCPRequest):
    """
    MCP streaming endpoint that handles multiple request types.
    Compatible with LLM tools that expect streaming responses.
    """
    method = request.method
    params = request.params
    
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
                    "version": "1.0.0"
                }
            }
            
        elif method == "tools/list":
            # List available tools
            tools = [
                {
                    "name": "init_crawl",
                    "description": "Initialize a new web crawl job for documentation",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Library/framework name"},
                            "start_urls": {"type": "array", "items": {"type": "string"}},
                            "max_depth": {"type": "integer", "default": 1, "minimum": 0, "maximum": 3},
                            "domain_filter": {"type": "string"},
                            "metadata": {"type": "object"}
                        },
                        "required": ["name", "start_urls"]
                    }
                },
                {
                    "name": "get_sources",
                    "description": "Get list of available libraries/sources with stats",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "job_id": {"type": "string", "description": "Optional specific job ID"}
                        }
                    }
                },
                {
                    "name": "search_content",
                    "description": "Search code snippets across all sources or in a specific library",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for content"},
                            "source": {"type": "string", "description": "Optional library name filter"},
                            "language": {"type": "string", "description": "Optional language filter"},
                            "max_results": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_snippet_details",
                    "description": "Get detailed information about a specific code snippet by ID",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "snippet_id": {"type": "integer", "description": "The ID of the snippet (from search results)"}
                        },
                        "required": ["snippet_id"]
                    }
                }
            ]
            response_data = {"tools": tools}
            
        elif method == "tools/call":
            # Execute a tool (MCP protocol uses tools/call)
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if not tool_name:
                raise ValueError("Tool name is required")
            
            # Execute the appropriate tool
            if tool_name == "init_crawl":
                result = await mcp_tools.init_crawl(**tool_args)
            elif tool_name == "get_sources":
                result = await mcp_tools.get_sources(**tool_args)
            elif tool_name == "search_content":
                result = await mcp_tools.search_content(**tool_args)
            elif tool_name == "get_snippet_details":
                result = await mcp_tools.get_snippet_details(**tool_args)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
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
            
            # Execute the appropriate tool
            if tool_name == "init_crawl":
                result = await mcp_tools.init_crawl(**tool_params)
            elif tool_name == "get_sources":
                result = await mcp_tools.get_sources(**tool_params)
            elif tool_name == "search_content":
                result = await mcp_tools.search_content(**tool_params)
            elif tool_name == "get_snippet_details":
                result = await mcp_tools.get_snippet_details(**tool_params)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
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