"""
AeroPark Smart System - WebSocket Router
Handles real-time WebSocket connections for parking updates.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging
import json

from services.websocket_service import get_websocket_manager
from services.parking_service import get_parking_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    tags=["WebSocket"]
)


@router.websocket("/ws/parking")
async def parking_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time parking updates.
    
    Clients connect to this endpoint to receive live updates about:
    - Parking spot status changes
    - New reservations
    - Reservation expirations
    - Sensor updates
    
    Query Parameters:
        token: Optional Firebase auth token for authenticated sessions
        
    Message Types Received:
        - connected: Initial connection confirmation
        - parking_status: Full parking status update
        - spot_update: Individual spot status change
        - reservation_created: New reservation made
        - reservation_expired: Reservation timeout
        - sensor_update: ESP32 sensor status change
    """
    manager = get_websocket_manager()
    
    try:
        # Accept the connection
        await manager.connect(websocket)
        
        # Send initial parking status
        try:
            service = get_parking_service()
            status = await service.get_parking_status()
            await websocket.send_json({
                "type": "initial_status",
                "data": status.model_dump(),
                "message": "Current parking status"
            })
        except Exception as e:
            logger.error(f"Error sending initial status: {e}")
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_text()
                
                # Parse and handle client messages
                try:
                    message = json.loads(data)
                    await handle_client_message(websocket, message)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON format"
                    })
                    
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        
    finally:
        await manager.disconnect(websocket)


async def handle_client_message(websocket: WebSocket, message: dict):
    """
    Handle incoming messages from WebSocket clients.
    
    Supports commands like:
    - ping: Keep-alive ping
    - subscribe: Subscribe to specific spot updates
    - get_status: Request current parking status
    
    Args:
        websocket: The client WebSocket connection
        message: Parsed message from client
    """
    msg_type = message.get("type", "unknown")
    
    if msg_type == "ping":
        # Respond to keep-alive ping
        await websocket.send_json({
            "type": "pong",
            "timestamp": message.get("timestamp")
        })
        
    elif msg_type == "get_status":
        # Send current parking status
        try:
            service = get_parking_service()
            status = await service.get_parking_status()
            await websocket.send_json({
                "type": "parking_status",
                "data": status.model_dump()
            })
        except Exception as e:
            logger.error(f"Error fetching status: {e}")
            await websocket.send_json({
                "type": "error",
                "message": "Error fetching parking status"
            })
            
    elif msg_type == "subscribe":
        # Handle subscription to specific spots
        spot_ids = message.get("spot_ids", [])
        await websocket.send_json({
            "type": "subscribed",
            "spot_ids": spot_ids,
            "message": f"Subscribed to {len(spot_ids)} spots"
        })
        
    else:
        # Unknown message type
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        })


@router.get(
    "/ws/status",
    tags=["WebSocket"],
    summary="WebSocket Status",
    description="Get current WebSocket connection statistics."
)
async def websocket_status():
    """
    Get WebSocket connection statistics.
    
    Returns the number of active WebSocket connections.
    Useful for monitoring and debugging.
    """
    manager = get_websocket_manager()
    
    return {
        "active_connections": manager.get_connection_count(),
        "status": "operational"
    }
