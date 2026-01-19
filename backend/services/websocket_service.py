"""
AeroPark Smart System - WebSocket Service
Manages WebSocket connections for real-time parking updates.
"""

from fastapi import WebSocket
from typing import List, Dict, Any, Optional
import json
import asyncio
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections and broadcasting.
    Provides real-time updates to all connected clients.
    """
    
    def __init__(self):
        # Active WebSocket connections
        self.active_connections: List[WebSocket] = []
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket):
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to register
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")
        
        # Send welcome message
        await self._send_to_socket(websocket, {
            "type": "connected",
            "message": "Connected to AeroPark real-time updates",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to remove
        """
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: Message dictionary to broadcast
        """
        if not self.active_connections:
            return
        
        disconnected = []
        
        async with self._lock:
            for websocket in self.active_connections:
                try:
                    await self._send_to_socket(websocket, message)
                except Exception as e:
                    logger.error(f"Error sending to websocket: {e}")
                    disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            await self.disconnect(ws)
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """
        Send a message to a specific user.
        Note: Requires user tracking implementation.
        
        Args:
            user_id: Target user ID
            message: Message to send
        """
        # For now, broadcast to all
        # TODO: Implement user-specific messaging with authenticated connections
        await self.broadcast(message)
    
    async def broadcast_parking_status(self, status_data: Dict[str, Any]):
        """
        Broadcast full parking status update.
        
        Args:
            status_data: Complete parking status
        """
        message = {
            "type": "parking_status",
            "data": status_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)
    
    async def broadcast_spot_update(self, spot_data: Dict[str, Any], event_type: str):
        """
        Broadcast a single spot update.
        
        Args:
            spot_data: Updated spot data
            event_type: Type of update (reserved, released, occupied, etc.)
        """
        message = {
            "type": "spot_update",
            "event": event_type,
            "data": spot_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)
    
    async def _send_to_socket(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Send a message to a specific WebSocket.
        
        Args:
            websocket: Target WebSocket
            message: Message to send
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            raise
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)


# Singleton instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """
    Get the WebSocketManager singleton instance.
    
    Returns:
        WebSocketManager: The global WebSocket manager
    """
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
