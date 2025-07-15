"""WebSocket support for real-time updates."""

import json
import logging
from typing import Dict, Set, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # client_id -> set of job_ids
    
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = set()
        logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            del self.subscriptions[client_id]
            logger.info(f"Client {client_id} disconnected")
    
    async def send_message(self, client_id: str, message: Dict[str, Any]) -> None:
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def broadcast_to_subscribers(self, job_id: str, message: Dict[str, Any]) -> None:
        """Broadcast a message to clients subscribed to a specific job."""
        disconnected_clients = []
        
        for client_id, job_ids in self.subscriptions.items():
            if job_id in job_ids:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to subscriber {client_id}: {e}")
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    def subscribe(self, client_id: str, job_id: str) -> None:
        """Subscribe a client to updates for a specific job."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].add(job_id)
            logger.info(f"Client {client_id} subscribed to job {job_id}")
    
    def unsubscribe(self, client_id: str, job_id: str) -> None:
        """Unsubscribe a client from updates for a specific job."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].discard(job_id)
            logger.info(f"Client {client_id} unsubscribed from job {job_id}")


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    """WebSocket endpoint handler."""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive and process messages
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "subscribe":
                    job_id = message.get("job_id")
                    if job_id:
                        manager.subscribe(client_id, job_id)
                        await manager.send_message(client_id, {
                            "type": "subscribed",
                            "job_id": job_id
                        })
                
                elif message_type == "unsubscribe":
                    job_id = message.get("job_id")
                    if job_id:
                        manager.unsubscribe(client_id, job_id)
                        await manager.send_message(client_id, {
                            "type": "unsubscribed",
                            "job_id": job_id
                        })
                
                elif message_type == "ping":
                    await manager.send_message(client_id, {"type": "pong"})
                
                else:
                    await manager.send_message(client_id, {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })
                    
            except json.JSONDecodeError:
                await manager.send_message(client_id, {
                    "type": "error",
                    "message": "Invalid JSON"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)


async def notify_crawl_update(job_id: str, status: str, data: Dict[str, Any]) -> None:
    """Notify subscribers about crawl job updates."""
    message = {
        "type": "crawl_update",
        "job_id": job_id,
        "status": status,
        "data": data,
        "timestamp": data.get("timestamp", "")
    }
    
    await manager.broadcast_to_subscribers(job_id, message)