"""
AeroPark Smart System - Service WebSocket
Gère les connexions WebSocket pour les mises à jour en temps réel.
Notifie l'ESP32 des nouvelles réservations.
"""

from fastapi import WebSocket
from typing import List, Dict, Any, Optional
import asyncio
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Gestionnaire de connexions WebSocket.
    Fournit des mises à jour en temps réel à tous les clients connectés.
    Envoie les notifications de réservation à l'ESP32.
    """
    
    def __init__(self):
        # Connexions WebSocket actives
        self.active_connections: List[WebSocket] = []
        # Lock pour les opérations thread-safe
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket):
        """
        Accepte et enregistre une nouvelle connexion WebSocket.
        
        Args:
            websocket: La connexion WebSocket à enregistrer
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        
        logger.info(f"Nouvelle connexion WebSocket. Total: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """
        Supprime une connexion WebSocket.
        
        Args:
            websocket: La connexion WebSocket à supprimer
        """
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        
        logger.info(f"WebSocket déconnecté. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Diffuse un message à tous les clients connectés.
        
        Args:
            message: Dictionnaire du message à diffuser
        """
        if not self.active_connections:
            return
        
        disconnected = []
        
        async with self._lock:
            for websocket in self.active_connections:
                try:
                    await self._send_to_socket(websocket, message)
                except Exception as e:
                    logger.error(f"Erreur d'envoi websocket: {e}")
                    disconnected.append(websocket)
        
        # Nettoyer les clients déconnectés
        for ws in disconnected:
            await self.disconnect(ws)
    
    async def notify_reservation(self, place_id: str, action: str):
        """
        Notifie l'ESP32 d'une nouvelle réservation ou annulation.
        
        Format envoyé (compris par l'ESP32):
        {
            "type": "reservation",
            "donnees": {
                "place_id": 1,
                "action": "create" ou "cancel"
            }
        }
        
        Args:
            place_id: ID de la place (ex: "a1", "a2")
            action: "create" ou "cancel"
        """
        # Extraire le numéro de place (a1 -> 1, a2 -> 2, etc.)
        try:
            place_number = int(place_id.replace("a", ""))
        except ValueError:
            place_number = 0
        
        message = {
            "type": "reservation",
            "donnees": {
                "place_id": place_number,
                "action": action
            }
        }
        
        logger.info(f"Notification réservation: place {place_id}, action {action}")
        await self.broadcast(message)
    
    async def broadcast_place_update(self, place_data: Dict[str, Any]):
        """
        Diffuse une mise à jour de place.
        
        Args:
            place_data: Données de la place mise à jour
        """
        message = {
            "type": "place_update",
            "place": place_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)
    
    async def _send_to_socket(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Envoie un message à un WebSocket spécifique.
        
        Args:
            websocket: WebSocket cible
            message: Message à envoyer
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Échec d'envoi du message WebSocket: {e}")
            raise
    
    def get_connection_count(self) -> int:
        """Retourne le nombre de connexions actives."""
        return len(self.active_connections)
    
    async def broadcast_parking_status(self, status: Dict[str, Any]):
        """
        Diffuse le statut complet du parking à tous les clients.
        
        Args:
            status: Dictionnaire avec le statut du parking
        """
        # Convertir les timestamps Firebase en strings
        if "places" in status:
            safe_places = []
            for p in status["places"]:
                safe_place = {}
                for k, v in p.items():
                    if hasattr(v, 'isoformat'):
                        safe_place[k] = v.isoformat()
                    else:
                        safe_place[k] = v
                safe_places.append(safe_place)
            status["places"] = safe_places
        
        status["timestamp"] = datetime.utcnow().isoformat()
        await self.broadcast(status)


# Instance singleton
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """
    Obtient l'instance singleton du WebSocketManager.
    
    Returns:
        WebSocketManager: Le gestionnaire WebSocket global
    """
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
