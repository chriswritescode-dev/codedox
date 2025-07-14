"""MCP Streamable HTTP Transport implementation."""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Union
from fastapi import Request, Response, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse
# Use FastAPI's StreamingResponse for SSE instead of MCP's EventSourceResponse
# to avoid the asyncio event loop issues in tests
from pydantic import BaseModel
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.shared.exceptions import McpError

logger = logging.getLogger(__name__)


class JSONRPCMessage(BaseModel):
    """JSON-RPC 2.0 message format."""
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: Optional[str] = None
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class StreamableTransport:
    """MCP Streamable HTTP Transport implementation."""
    
    def __init__(self, server: Server):
        self.server = server
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    async def handle_request(
        self,
        request: Request,
        mcp_session_id: Optional[str] = Header(None),
        accept: str = Header(None),
        origin: Optional[str] = Header(None),
        last_event_id: Optional[str] = Header(None)
    ) -> Response:
        """Handle incoming MCP streamable HTTP requests."""
        
        # Validate Accept header
        if not accept or not all(ct in accept for ct in ["application/json", "text/event-stream"]):
            raise HTTPException(
                status_code=406,
                detail="Accept header must include both application/json and text/event-stream"
            )
        
        # Validate Origin for security
        if origin and not self._is_origin_allowed(origin):
            raise HTTPException(status_code=403, detail="Origin not allowed")
        
        # Parse request body
        try:
            body = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        
        # Handle single message or batch
        messages = body if isinstance(body, list) else [body]
        
        # Validate messages
        for msg in messages:
            if not isinstance(msg, dict) or "jsonrpc" not in msg or msg["jsonrpc"] != "2.0":
                raise HTTPException(status_code=400, detail="Invalid JSON-RPC 2.0 message")
        
        # Process messages
        responses = []
        
        for msg in messages:
            try:
                response = await self._process_message(msg, mcp_session_id)
                if response:
                    responses.append(response)
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                if "id" in msg:
                    responses.append({
                        "jsonrpc": "2.0",
                        "id": msg["id"],
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        }
                    })
        
        # Determine response type based on Accept header preference
        accept_types = [t.strip() for t in accept.split(",")]
        prefers_sse = accept_types[0] == "text/event-stream"
        
        if prefers_sse and responses:
            # Return SSE stream when client explicitly prefers SSE
            return StreamingResponse(
                self._create_event_stream(responses, mcp_session_id, last_event_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-store",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        elif responses:
            # Return JSON response (default for streamable transport)
            if len(responses) == 1 and not isinstance(body, list):
                return JSONResponse(content=responses[0])
            else:
                return JSONResponse(content=responses)
        else:
            # No responses (notifications only)
            return Response(status_code=202)
    
    async def _process_message(
        self,
        msg: Dict[str, Any],
        session_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Process a single JSON-RPC message."""
        
        method = msg.get("method")
        params = msg.get("params", {})
        msg_id = msg.get("id")
        
        # This is a notification if no ID
        is_notification = msg_id is None
        
        try:
            if method == "initialize":
                # Handle initialization
                session_id = session_id or str(uuid.uuid4())
                self.sessions[session_id] = {
                    "initialized": True,
                    "client_info": params.get("clientInfo", {})
                }
                
                # Initialize server if not already done
                # Note: The server handles initialization internally
                
                if not is_notification:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {
                                "tools": {}
                            },
                            "serverInfo": {
                                "name": "codedox-mcp",
                                "version": "1.0.0"
                            }
                        }
                    }
                    
            elif method == "tools/list":
                # Use our MCP tools directly
                from ..mcp_server.tools import MCPTools
                mcp_tools = MCPTools()
                
                # Create tool definitions manually
                tools = [
                    {
                        "name": "init_crawl",
                        "description": "Initialize a new web crawl job for documentation",
                        "inputSchema": {
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
                        "inputSchema": {
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
                        "inputSchema": {
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
                        "inputSchema": {
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
                
                if not is_notification:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "tools": tools
                        }
                    }
                    
            elif method == "tools/call":
                # Execute tool
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                
                # Use our MCP tools directly
                from ..mcp_server.tools import MCPTools
                mcp_tools = MCPTools()
                
                if tool_name == "init_crawl":
                    result = await mcp_tools.init_crawl(
                        name=tool_args["name"],
                        start_urls=tool_args["start_urls"],
                        max_depth=tool_args.get("max_depth", 1),
                        domain_filter=tool_args.get("domain_filter"),
                        metadata=tool_args.get("metadata", {})
                    )
                elif tool_name == "get_sources":
                    result = await mcp_tools.get_sources(
                        job_id=tool_args.get("job_id")
                    )
                elif tool_name == "search_content":
                    result = await mcp_tools.search_content(
                        query=tool_args["query"],
                        source=tool_args.get("source"),
                        language=tool_args.get("language"),
                        max_results=tool_args.get("max_results", 10)
                    )
                elif tool_name == "get_snippet_details":
                    result = await mcp_tools.get_snippet_details(
                        snippet_id=tool_args["snippet_id"]
                    )
                else:
                    raise McpError(f"Unknown tool: {tool_name}")
                
                # Format result as text content
                if isinstance(result, str):
                    content = [{"type": "text", "text": result}]
                else:
                    content = [{"type": "text", "text": json.dumps(result, indent=2)}]
                
                if not is_notification:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": content
                        }
                    }
                    
            else:
                # Unknown method
                if not is_notification:
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }
                    
        except McpError as e:
            if not is_notification:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32000,
                        "message": str(e)
                    }
                }
        except Exception as e:
            logger.error(f"Error handling {method}: {e}")
            if not is_notification:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                }
        
        return None
    
    async def _create_event_stream(  # type: ignore[no-untyped-def]
        self,
        initial_responses: List[Dict[str, Any]],
        session_id: Optional[str],
        last_event_id: Optional[str]
    ):
        """Create an SSE event stream."""
        
        # Send initial responses
        event_id = int(last_event_id) if last_event_id else 0
        
        for response in initial_responses:
            event_id += 1
            # Format as proper SSE
            sse_data = f"id: {event_id}\r\nevent: message\r\ndata: {json.dumps(response)}\r\n\r\n"
            yield sse_data
        
        # Send done event to close stream
        yield "event: done\r\ndata: \r\n\r\n"
    
    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if the origin is allowed."""
        # For development, allow localhost origins
        allowed_origins = [
            "http://localhost",
            "https://localhost",
            "http://127.0.0.1",
            "https://127.0.0.1"
        ]
        
        for allowed in allowed_origins:
            if origin.startswith(allowed):
                return True
        
        return False