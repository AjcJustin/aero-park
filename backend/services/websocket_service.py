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
        
        # Convertir les DatetimeWithNanoseconds en ISO strings
        message = self._make_json_safe(message)
        
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
    
    def _make_json_safe(self, obj: Any) -> Any:
        """
        Convertit récursivement les objets non-JSON-serializable en formats sûrs.
        Gère spécifiquement les DatetimeWithNanoseconds de Firestore.
        
        Args:
            obj: Objet à convertir
            
        Returns:
            Objet JSON-serializable
        """
        if isinstance(obj, dict):
            return {k: self._make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_safe(item) for item in obj]
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        elif hasattr(obj, 'to_datetime'):  # Firebase Timestamp
            return obj.to_datetime().isoformat()
        else:
            return obj
    
    async def notify_reservation(self, place_id: str, action: str, updated_place_data: Optional[Dict[str, Any]] = None):
        """
        Notifie l'ESP32 d'une nouvelle réservation ou annulation.
        Maintenant diffuse le statut complet pour mise à jour LCD immédiate.
        Gère l'éventuelle consistance de Firestore via updated_place_data.
        """
        # Obtenir toutes les places pour le broadcast complet
        from database.firebase_db import get_db
        db = get_db()
        places = await db.get_all_places()
        
        # Si on a des données manuelles, on les injecte (fix eventual consistency)
        if updated_place_data:
            # Trouver et remplacer la place dans la liste
            for i, p in enumerate(places):
                if p.get("place_id") == place_id or p.get("id") == place_id:
                    # Fusionner ou remplacer
                    places[i] = {**p, **updated_place_data}
                    break
            else:
                # Si non trouvée (ex: création dynamique?), on l'ajoute
                places.append(updated_place_data)
        
        # Recalculer les stats avec les données fraîches
        total = len(places)
        free = sum(1 for p in places if p.get("etat") == "free")
        reserved = sum(1 for p in places if p.get("etat") == "reserved")
        occupied = sum(1 for p in places if p.get("etat") == "occupied")
        
        # ========================================================================
        # STRATÉGIE DE BROADCAST EN 4 ÉTAPES POUR COMPATIBILITÉ MAXIMALE
        # ========================================================================
        
        # ÉTAPE 0: Message PARKING_UPDATE pour ESP32 ACTUEL (compatibilité immédiate)
        # Ce format fonctionne avec le code ESP32 existant SANS modification
        old_esp32_message = {
            "type": "parking_update",
            "places": places[:6]  # Limiter à 6 places pour réduire la taille
        }
        
        logger.info(f"📟 ESP32 Compat: Envoi parking_update avec {len(places[:6])} places")
        await self.broadcast(old_esp32_message)
        
        # Petit délai
        import asyncio
        await asyncio.sleep(0.1)
        
        # ÉTAPE 1: Message ULTRA-LÉGER pour ESP32/LCD (< 200 octets)
        # Pour le nouveau code ESP32 optimisé
        lcd_message = {
            "type": "lcd_update",
            "free": free,
            "total": total,
            "occupied": occupied,
            "reserved": reserved
        }
        
        logger.info(f"📺 LCD Update: {free}/{total} libres")
        await self.broadcast(lcd_message)
        
        await asyncio.sleep(0.1)
        
        # ÉTAPE 2: Message LEGACY pour compatibilité anciens systèmes
        if action in ["create", "cancel", "admin_release", "sensor_update", "reserve"]:
            # Convertir P1 -> 1 pour l'ESP32 legacy
            numeric_id = place_id
            if isinstance(place_id, str):
                import re
                match = re.search(r'\d+', place_id)
                if match:
                    try:
                        numeric_id = int(match.group())
                    except:
                        pass
            
            # Déterminer l'action
            legacy_action = "cancel"
            if action in ["create", "reserve"]:
                legacy_action = "reserve"
            elif action == "sensor_update" and updated_place_data:
                legacy_action = "create" if updated_place_data.get("etat") == "occupied" else "cancel"
                
            legacy_message = {
                "type": "reservation",
                "place_id": numeric_id,
                "action": legacy_action,
                "free": free,
                "total": total
            }
            
            await asyncio.sleep(0.1)
            await self.broadcast(legacy_message)
            logger.info(f"📡 Legacy: place {numeric_id} action {legacy_action}")
        
        # ÉTAPE 3: Message COMPLET pour dashboard web (avec toutes les données)
        # Ce message est volumineux mais les navigateurs web peuvent le gérer
        full_status = {
            "type": "status_update",
            "total_places": total,
            "libres": free,
            "reservees": reserved,
            "occupees": occupied,
            "free_spots": free,
            "occupied_spots": occupied,
            "reserved_spots": reserved,
            "total_spots": total,
            "available": free,
            "places": places,  # Tableau complet pour le dashboard
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await asyncio.sleep(0.1)
        await self.broadcast_parking_status(full_status)

    async def notify_code_validated(self, code: str, place_id: Optional[str] = None):
        """
        Notifie l'ESP32 qu'un code a été validé via le frontend.
        L'ESP32 pourra alors ouvrir la barrière quand le capteur détectera la voiture.
        """
        message = {
            "type": "code_validated",
            "code": code,
            "place_id": place_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"Code {code} validé via frontend. Notification ESP32 envoyée.")
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

    async def broadcast_settings_update(self, settings: Dict[str, Any]):
        """
        Diffuse une mise à jour des paramètres.
        """
        message = {
            "type": "settings_update",
            "settings": settings,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(message)
    
    def get_connection_count(self) -> int:
        """Retourne le nombre de connexions actives."""
        return len(self.active_connections)
    
    async def broadcast_parking_status(self, status: Dict[str, Any]):
        """
        Diffuse le statut complet du parking à tous les clients.
        Assure la compatibilité avec l'affichage LCD de l'ESP32.
        
        Args:
            status: Dictionnaire avec le statut du parking
        """
        # S'assurer que le type est correct pour l'ESP32 if not specified
        if "type" not in status or status["type"] == "parking_update":
            status["type"] = "status_update"
            
        # Ajouter les clés de compatibilité LCD (Français + English variants)
        # Français (Existing)
        if "free" in status: status["libres"] = status["free"]
        if "occupied" in status: status["occupees"] = status["occupied"]
        if "reserved" in status: status["reservees"] = status["reserved"]
        if "total" in status: status["total_places"] = status["total"]
        
        # English Variants (for ESP32 and specific LCD code)
        status["free_spots"] = status.get("free", status.get("libres", 0))
        status["occupied_spots"] = status.get("occupied", status.get("occupees", 0))
        status["reserved_spots"] = status.get("reserved", status.get("reservees", 0))
        status["total_spots"] = status.get("total", status.get("total_places", 0))
        
        # Available key
        status["available"] = status.get("free", status.get("libres", 0))

        # Cas inverse: si on a les clés françaises mais pas anglaises
        if "libres" in status and "free" not in status: status["free"] = status["libres"]
        if "occupees" in status and "occupied" not in status: status["occupied"] = status["occupees"]
        if "reservees" in status and "reserved" not in status: status["reserved"] = status["reservees"]
        if "total_places" in status and "total" not in status: status["total"] = status["total_places"]

        # Convertir les timestamps Firebase en strings pour les places
        if "places" in status:
            safe_places = []
            for p in status["places"]:
                safe_place = {}
                for k, v in p.items():
                    # Gérer les types datetime ou Firestore Timestamp
                    if hasattr(v, 'isoformat'):
                        safe_place[k] = v.isoformat()
                    elif hasattr(v, 'to_datetime'): # Firebase Timestamp
                        safe_place[k] = v.to_datetime().isoformat()
                    else:
                        safe_place[k] = v
                safe_places.append(safe_place)
            status["places"] = safe_places
        
        status["timestamp"] = datetime.utcnow().isoformat()
        
        logger.info(f"Broadcast statut parking: Libres={status.get('libres')}, Occupées={status.get('occupees')}")
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
