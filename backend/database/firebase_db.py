"""
AeroPark Smart System - Firebase Database Module
Gestion des opérations Firebase Firestore pour le parking.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import FieldFilter
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Global Firebase app instance
_firebase_app: Optional[firebase_admin.App] = None
_firestore_client = None


def init_firebase() -> firebase_admin.App:
    """
    Initialise Firebase Admin SDK.
    Appelé une seule fois au démarrage de l'application.
    """
    global _firebase_app, _firestore_client
    
    if _firebase_app is not None:
        logger.info("Firebase déjà initialisé")
        return _firebase_app
    
    try:
        settings = get_settings()
        cred = credentials.Certificate(settings.get_firebase_credentials())
        
        _firebase_app = firebase_admin.initialize_app(cred)
        _firestore_client = firestore.client()
        logger.info("Firebase initialisé avec succès")
        
        return _firebase_app
        
    except Exception as e:
        logger.error(f"Échec de l'initialisation Firebase: {e}")
        raise


def get_firestore_client():
    """Obtient l'instance du client Firestore."""
    global _firestore_client
    if _firestore_client is None:
        init_firebase()
    return _firestore_client


class FirebaseDB:
    """
    Gestionnaire de base de données Firebase Firestore.
    Fournit toutes les opérations CRUD pour la gestion du parking.
    """
    
    COLLECTION_PLACES = "parking_places"
    COLLECTION_RESERVATIONS = "reservations"
    COLLECTION_USERS = "users"
    
    def __init__(self):
        self.db = get_firestore_client()
    
    # ==================== PLACES DE PARKING ====================
    
    async def get_all_places(self) -> List[Dict[str, Any]]:
        """Récupère toutes les places de parking."""
        try:
            places_ref = self.db.collection(self.COLLECTION_PLACES)
            docs = places_ref.order_by("place_id").stream()
            
            places = []
            for doc in docs:
                place_data = doc.to_dict()
                places.append(place_data)
            
            return places
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des places: {e}")
            raise
    
    async def get_place_by_id(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une place par son ID (ex: a1, a2)."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_PLACES).document(place_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la place {place_id}: {e}")
            raise
    
    async def update_place_status(
        self,
        place_id: str,
        etat: str,
        force_signal: int = None
    ) -> Dict[str, Any]:
        """
        Met à jour l'état d'une place depuis le capteur ESP32.
        Gère les transitions RESERVED → OCCUPIED et OCCUPIED → FREE.
        """
        try:
            place = await self.get_place_by_id(place_id)
            
            if not place:
                # Créer la place si elle n'existe pas
                place = {
                    "place_id": place_id,
                    "etat": etat,
                    "reserved_by": None,
                    "reserved_by_email": None,
                    "reservation_start_time": None,
                    "reservation_end_time": None,
                    "force_signal": force_signal,
                    "last_update": datetime.utcnow()
                }
                self.db.collection(self.COLLECTION_PLACES).document(place_id).set(place)
                logger.info(f"Place {place_id} créée avec état {etat}")
                return {"etat": etat, "transition": "created"}
            
            current_etat = place.get("etat", "free")
            now = datetime.utcnow()
            
            updates = {
                "force_signal": force_signal,
                "last_update": now
            }
            
            transition = None
            
            if etat == "occupied":
                if current_etat == "reserved":
                    # Véhicule arrivé sur place réservée
                    updates["etat"] = "occupied"
                    transition = "reserved->occupied"
                elif current_etat == "free":
                    # Véhicule sans réservation
                    updates["etat"] = "occupied"
                    transition = "free->occupied"
                # Si déjà occupied, pas de changement
                    
            elif etat == "free":
                if current_etat == "occupied":
                    # Véhicule parti
                    updates["etat"] = "free"
                    updates["reserved_by"] = None
                    updates["reserved_by_email"] = None
                    updates["reservation_start_time"] = None
                    updates["reservation_end_time"] = None
                    transition = "occupied->free"
                elif current_etat == "reserved":
                    # Place réservée mais pas de véhicule (normal)
                    pass
            
            if updates:
                self.db.collection(self.COLLECTION_PLACES).document(place_id).update(updates)
            
            new_etat = updates.get("etat", current_etat)
            logger.info(f"Place {place_id}: {current_etat} -> {new_etat}")
            
            return {"etat": new_etat, "transition": transition}
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la place: {e}")
            raise
    
    async def reserve_place(
        self,
        place_id: str,
        user_id: str,
        user_email: str,
        duration_minutes: int
    ) -> Dict[str, Any]:
        """
        Réserve une place de parking.
        Utilise une transaction Firestore pour éviter les conflits.
        """
        transaction = self.db.transaction()
        place_ref = self.db.collection(self.COLLECTION_PLACES).document(place_id)
        
        @firestore.transactional
        def reserve_in_transaction(transaction) -> Dict[str, Any]:
            place_doc = place_ref.get(transaction=transaction)
            
            if not place_doc.exists:
                raise ValueError(f"Place {place_id} non trouvée")
            
            place_data = place_doc.to_dict()
            
            if place_data.get("etat") != "free":
                raise ValueError(f"Place non disponible. État actuel: {place_data.get('etat')}")
            
            now = datetime.utcnow()
            end_time = now + timedelta(minutes=duration_minutes)
            
            updates = {
                "etat": "reserved",
                "reserved_by": user_id,
                "reserved_by_email": user_email,
                "reservation_start_time": now,
                "reservation_end_time": end_time,
                "reservation_duration_minutes": duration_minutes,
                "last_update": now
            }
            
            transaction.update(place_ref, updates)
            
            return {**place_data, **updates}
        
        try:
            result = reserve_in_transaction(transaction)
            logger.info(f"Place {place_id} réservée pour {user_id}")
            return result
        except Exception as e:
            logger.error(f"Échec de la réservation: {e}")
            raise
    
    async def release_place(self, place_id: str) -> bool:
        """Libère une place de parking."""
        try:
            updates = {
                "etat": "free",
                "reserved_by": None,
                "reserved_by_email": None,
                "reservation_start_time": None,
                "reservation_end_time": None,
                "reservation_duration_minutes": None,
                "last_update": datetime.utcnow()
            }
            
            self.db.collection(self.COLLECTION_PLACES).document(place_id).update(updates)
            logger.info(f"Place {place_id} libérée")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la libération de la place {place_id}: {e}")
            raise
    
    async def get_expired_reservations(self) -> List[Dict[str, Any]]:
        """Récupère les réservations expirées."""
        try:
            now = datetime.utcnow()
            
            places_ref = self.db.collection(self.COLLECTION_PLACES)
            query = places_ref.where(
                filter=FieldFilter("etat", "==", "reserved")
            ).where(
                filter=FieldFilter("reservation_end_time", "<", now)
            )
            
            docs = query.stream()
            expired = []
            for doc in docs:
                place_data = doc.to_dict()
                expired.append(place_data)
            
            return expired
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des réservations expirées: {e}")
            raise
    
    async def initialize_default_places(self, count: int = 6) -> List[str]:
        """
        Initialise les places de parking par défaut.
        Appelé au démarrage de l'application.
        """
        try:
            existing = await self.get_all_places()
            if existing:
                logger.info(f"{len(existing)} places existantes, initialisation ignorée")
                return []
            
            created_ids = []
            
            for i in range(1, count + 1):
                place_id = f"a{i}"
                place_data = {
                    "place_id": place_id,
                    "etat": "free",
                    "reserved_by": None,
                    "reserved_by_email": None,
                    "reservation_start_time": None,
                    "reservation_end_time": None,
                    "force_signal": None,
                    "last_update": datetime.utcnow()
                }
                self.db.collection(self.COLLECTION_PLACES).document(place_id).set(place_data)
                created_ids.append(place_id)
            
            logger.info(f"{count} places de parking initialisées")
            return created_ids
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation des places: {e}")
            raise
    
    # ==================== UTILISATEURS ====================
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Récupère le profil utilisateur."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_USERS).document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'utilisateur {user_id}: {e}")
            raise
    
    async def upsert_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """Crée ou met à jour le profil utilisateur."""
        try:
            profile_data["updated_at"] = datetime.utcnow()
            
            doc_ref = self.db.collection(self.COLLECTION_USERS).document(user_id)
            doc_ref.set(profile_data, merge=True)
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'utilisateur {user_id}: {e}")
            raise
    
    async def get_user_active_reservation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Récupère la réservation active de l'utilisateur."""
        try:
            places_ref = self.db.collection(self.COLLECTION_PLACES)
            query = places_ref.where(
                filter=FieldFilter("reserved_by", "==", user_id)
            ).where(
                filter=FieldFilter("etat", "in", ["reserved", "occupied"])
            ).limit(1)
            
            docs = query.stream()
            for doc in docs:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la réservation: {e}")
            raise


# Instance singleton
_db_instance: Optional[FirebaseDB] = None


def get_db() -> FirebaseDB:
    """Obtient l'instance singleton de FirebaseDB."""
    global _db_instance
    if _db_instance is None:
        _db_instance = FirebaseDB()
    return _db_instance
