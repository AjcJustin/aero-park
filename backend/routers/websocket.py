"""
AeroPark Smart System - WebSocket Router
Gère les connexions WebSocket en temps réel pour les mises à jour du parking.
L'ESP32 se connecte sur /ws/parking pour recevoir les notifications de réservation.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging
import json
from datetime import datetime

from services.websocket_service import get_websocket_manager
from database.firebase_db import get_db

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
    Point de terminaison WebSocket pour les mises à jour en temps réel.
    
    L'ESP32 se connecte ici pour recevoir:
    - Notifications de réservation (pour afficher sur LCD et ouvrir barrière)
    - Changements d'état des places
    
    Format des messages envoyés à l'ESP32:
    {
        "type": "reservation",
        "donnees": {
            "place_id": 1,  // Numéro de place (1-6)
            "action": "create" ou "cancel"
        }
    }
    """
    manager = get_websocket_manager()
    
    try:
        # Accepter la connexion
        await manager.connect(websocket)
        logger.info("Nouvelle connexion WebSocket établie")
        
        # Envoyer l'état initial du parking
        try:
            db = get_db()
            places = await db.get_all_places()
            
            # Convertir les timestamps Firebase en strings
            safe_places = []
            for p in places:
                safe_place = {}
                for k, v in p.items():
                    if hasattr(v, 'isoformat'):
                        safe_place[k] = v.isoformat()
                    else:
                        safe_place[k] = v
                safe_places.append(safe_place)
            
            await websocket.send_json({
                "type": "connected",
                "message": "Connexion établie à AeroPark",
                "places": safe_places,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Erreur envoi état initial: {e}")
        
        # Maintenir la connexion et gérer les messages
        while True:
            try:
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    await handle_client_message(websocket, message)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Format JSON invalide"
                    })
                    
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
        
    finally:
        await manager.disconnect(websocket)
        logger.info("Connexion WebSocket fermée")


async def handle_client_message(websocket: WebSocket, message: dict):
    """
    Gère les messages entrants des clients WebSocket.
    
    Commandes supportées:
    - ping: Maintien de connexion
    - get_status: Récupérer l'état actuel du parking
    
    Args:
        websocket: La connexion WebSocket du client
        message: Message parsé du client
    """
    msg_type = message.get("type", "unknown")
    
    if msg_type == "ping":
        # Répondre au ping keep-alive
        await websocket.send_json({
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    elif msg_type == "get_status":
        # Envoyer l'état actuel du parking
        try:
            db = get_db()
            places = await db.get_all_places()
            
            await websocket.send_json({
                "type": "parking_status",
                "places": places,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Erreur récupération état: {e}")
            await websocket.send_json({
                "type": "error",
                "message": "Erreur récupération état parking"
            })
    else:
        # Type de message inconnu
        await websocket.send_json({
            "type": "error",
            "message": f"Type de message inconnu: {msg_type}"
        })


@router.get(
    "/ws/status",
    tags=["WebSocket"],
    summary="État des connexions WebSocket",
    description="Obtenir les statistiques des connexions WebSocket."
)
async def websocket_status():
    """
    Obtenir les statistiques de connexion WebSocket.
    
    Retourne le nombre de connexions WebSocket actives.
    Utile pour le monitoring.
    """
    manager = get_websocket_manager()
    
    return {
        "active_connections": manager.get_connection_count(),
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }

