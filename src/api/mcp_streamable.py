"""MCP Streamable HTTP Transport implementation."""

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from mcp.server import Server
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from ..constants import __version__, __mcp_server_name__

# Use FastAPI's StreamingResponse for SSE instead of MCP's EventSourceResponse
# to avoid the asyncio event loop issues in tests
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp")


class JSONRPCMessage(BaseModel):
    """JSON-RPC 2.0 message format."""
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str | None = None
    params: dict[str, Any] | list[Any] | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None


# Create a single transport instance
transport = None

@router.post("")
async def handle_mcp_streamable_request(
    request: Request,
    mcp_session_id: str | None = Header(None),
    accept: str = Header(None),
    origin: str | None = Header(None),
    last_event_id: str | None = Header(None)
) -> Response:
    """Handle incoming MCP streamable HTTP requests."""
    global transport

    # Initialize transport if not already done
    if transport is None:
        from mcp.server import Server
        mcp_server: Server = Server("codedox")
        transport = StreamableTransport(mcp_server)

    return await transport.handle_request(
        request, mcp_session_id, accept, origin, last_event_id
    )


class StreamableTransport:
    """MCP Streamable HTTP Transport implementation."""

    def __init__(self, server: Server):
        self.server = server
        self.sessions: dict[str, dict[str, Any]] = {}

    async def handle_request(
        self,
        request: Request,
        mcp_session_id: str | None = Header(None),
        accept: str = Header(None),
        origin: str | None = Header(None),
        last_event_id: str | None = Header(None)
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
        msg: dict[str, Any],
        session_id: str | None
    ) -> dict[str, Any] | None:
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
                                "name": __mcp_server_name__,
                                "version": __version__
                            }
                        }
                    }

            elif method == "tools/list":
                # Get tool definitions from MCP server
                from ..mcp_server.server import MCPServer

                mcp_server = MCPServer()

                # Get tools from MCP server and convert to protocol format
                tool_defs = mcp_server.get_tool_definitions()
                tools = [
                    {
                        "name": tool["name"],
                        "description": tool["description"],
                        "inputSchema": tool["input_schema"],
                    }
                    for tool in tool_defs
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

                logger.info(f"Executing tool '{tool_name}' with args: {tool_args}")

                # Use MCP server for execution
                from ..mcp_server.server import MCPServer

                mcp_server = MCPServer()

                try:
                    result = await mcp_server.execute_tool(tool_name, tool_args)
                except ValueError as e:
                    logger.error(f"Tool execution failed for '{tool_name}': {e}")
                    raise McpError(ErrorData(code=-32601, message=f"Unknown tool: {tool_name}"))

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
            logger.error(f"MCP error in {method}: {e}")
            if not is_notification:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32000,
                        "message": str(e),
                        "data": {"method": method, "params": params},
                    },
                }
        except Exception as e:
            logger.error(f"Error handling {method}: {e}", exc_info=True)
            if not is_notification:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": {"detail": str(e), "method": method},
                    },
                }

        return None

    async def _create_event_stream(  # type: ignore[no-untyped-def]
        self,
        initial_responses: list[dict[str, Any]],
        session_id: str | None,
        last_event_id: str | None
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
