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
import re

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
    
    try:
        settings = get_settings()
        cred = credentials.Certificate(settings.get_firebase_credentials())
        
        # Si une application existe déjà, on essaie de la réutiliser ou de la recréer
        try:
            _firebase_app = firebase_admin.get_app()
            # Pour forcer la prise en compte des nouveaux paramètres du .env, 
            # on supprime l'ancienne instance si elle existe (en mode reload)
            firebase_admin.delete_app(_firebase_app)
            logger.info("Ancienne instance Firebase supprimée pour rechargement")
        except ValueError:
            pass # Pas d'application par défaut
            
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
    COLLECTION_SETTINGS = "settings"
    
    def __init__(self):
        self.db = get_firestore_client()

    async def get_settings(self) -> Dict[str, Any]:
        """Récupère les paramètres du système (depuis global)."""
        try:
            doc = self.db.collection(self.COLLECTION_SETTINGS).document("global").get()
            if doc.exists:
                return doc.to_dict()
            return {}
        except Exception as e:
            logger.error(f"Erreur récupération paramètres: {e}")
            return {}

    async def save_settings(self, settings: Dict[str, Any]) -> bool:
        """Sauvegarde les paramètres du système (dans global)."""
        try:
            settings["updated_at"] = datetime.utcnow()
            self.db.collection(self.COLLECTION_SETTINGS).document("global").set(settings, merge=True)
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde paramètres: {e}")
            raise
    
    # ==================== PLACES DE PARKING ====================
    
    async def get_all_places(self) -> List[Dict[str, Any]]:
        """Récupère toutes les places de parking (avec cache)."""
        import asyncio
        from database.firebase_cache import get_firebase_cache
        
        cache = get_firebase_cache()
        cache_key = "parking:all_places"
        
        # Try cache first (10 minute TTL)
        cached = cache.get(cache_key, ttl_seconds=600)
        if cached is not None:
            logger.debug("Returning cached parking places")
            return cached
        
        logger.info("Cache miss - fetching parking places from Firebase")
        
        def _get_places_sync():
            """Synchronous helper to fetch places from Firestore."""
            places_ref = self.db.collection(self.COLLECTION_PLACES)
            docs = places_ref.stream()
            
            places = []
            for doc in docs:
                place_data = doc.to_dict()
                place_data["id"] = doc.id
                place_data["place_id"] = doc.id
                
                # Convertir les timestamps pour le frontend
                # Convertir les timestamps pour le frontend
                for key in ["last_update", "reservation_start_time", "reservation_end_time"]:
                    val = place_data.get(key)
                    if val:
                        iso_str = ""
                        if hasattr(val, 'isoformat'):
                            iso_str = val.isoformat()
                        elif isinstance(val, str):
                            iso_str = val
                            
                        # Ensure UTC interpretation by frontend
                        if iso_str and not iso_str.endswith('Z') and '+' not in iso_str:
                            iso_str += 'Z'
                        
                        if iso_str:
                            place_data[key] = iso_str
                        
                places.append(place_data)
            
            # Natural Sort (Tri naturel) pour avoir P1, P2 ... P10 et non P1, P10, P2
            def natural_sort_key(s):
                return [int(text) if text.isdigit() else text.lower()
                        for text in re.split(r'(\d+)', s.get("place_id") or "")]
            
            places.sort(key=natural_sort_key)
            return places
        
        try:
            # Run blocking Firestore call in thread pool to avoid blocking event loop
            places = await asyncio.to_thread(_get_places_sync)
            
            # Store in cache for next request
            cache.set(cache_key, places)
            
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
                data = doc.to_dict()
                data["id"] = doc.id
                data["place_id"] = doc.id
                return data
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
                
                # Invalidate cache when a new place is created
                from database.firebase_cache import get_firebase_cache
                cache = get_firebase_cache()
                cache.invalidate("parking:all_places")
                logger.debug("Cache invalidated due to new place creation")
                
                return {"etat": etat, "transition": "created"}
            
            current_etat = place.get("etat", "free")
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
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
                    # Véhicule parti - Calculer et enregistrer la durée d'occupation
                    arrival_time = place.get("last_update") or place.get("start_time")
                    if arrival_time:
                        # Convert to datetime if it's a string
                        if isinstance(arrival_time, str):
                            arrival_time = datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
                        
                        # Ensure arrival_time is timezone-aware (for Firestore DatetimeWithNanoseconds)
                        if arrival_time.tzinfo is None:
                            from datetime import timezone
                            arrival_time = arrival_time.replace(tzinfo=timezone.utc)
                        
                        # Calculate duration in seconds for precise display
                        duration_seconds = (now - arrival_time).total_seconds()
                        duration_minutes = int(duration_seconds / 60)
                        
                        logger.info(f"DEBUG DURATION: Place={place_id}, Now={now}, Arrival={arrival_time}, Duration={duration_seconds}s ({duration_minutes}m)")
                        
                        # DEBUG EXPLICITE DANS UN FICHIER
                        try:
                            with open("debug_duration.log", "a") as f:
                                f.write(f"DEBUG: {now} - Place {place_id} - Arrival {arrival_time} - Duration {duration_seconds}s\n")
                        except Exception as e:
                            logger.error(f"Failed to write debug log: {e}")

                        # Pour éviter des durées négatives ou absurdes si last_update est vieux
                        if duration_seconds > 0:
                            updates["last_occupancy_duration_seconds"] = int(duration_seconds)
                            updates["last_occupancy_duration_minutes"] = duration_minutes  # Keep for compatibility
                            updates["last_occupancy_end_time"] = now
                            logger.info(f"Place {place_id}: Enregistrement durée occupation = {int(duration_seconds)}s ({duration_minutes}m)")
                        else:
                            logger.warning(f"Place {place_id}: Durée négative ou nulle ({duration_seconds}), pas d'enregistrement.")
                    
                    updates["etat"] = "free"
                    updates["reserved_by"] = None
                    updates["reserved_by_email"] = None
                    updates["reservation_start_time"] = None
                    updates["reservation_end_time"] = None
                    transition = "occupied->free"
                elif current_etat == "reserved":
                    # FIX: Capteur détecte qu'il n'y a plus de véhicule sur une place réservée
                    # Cela peut arriver si:
                    # - La réservation a expiré mais la voiture était déjà là
                    # - Le capteur détecte le départ après que l'état soit repassé en reserved
                    
                    # Calculer la durée comme pour 'occupied -> free'
                    # On utilise 'last_update' qui devrait correspondre à l'arrivée (si la transition reserved->occupied a eu lieu)
                    # Ou 'start_time' de la réservation
                    arrival_time = place.get("last_update") or place.get("start_time") or place.get("reservation_start_time")
                    
                    if arrival_time:
                         # Convert to datetime if it's a string
                        if isinstance(arrival_time, str):
                            arrival_time = datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
                        
                        # Ensure arrival_time is timezone-aware
                        if arrival_time.tzinfo is None:
                            from datetime import timezone
                            arrival_time = arrival_time.replace(tzinfo=timezone.utc)
                        
                        # Calculate duration in seconds for precise display
                        duration_seconds = (now - arrival_time).total_seconds()
                        duration_minutes = int(duration_seconds / 60)
                        
                        logger.info(f"DEBUG DURATION: Place={place_id}, Now={now}, Arrival={arrival_time}, Duration={duration_seconds}s")
                        
                        # DEBUG EXPLICITE DANS UN FICHIER
                        try:
                            with open("debug_duration.log", "a") as f:
                                f.write(f"DEBUG: {now} - Place {place_id} - Arrival {arrival_time} - Duration {duration_seconds}s\n")
                        except Exception as e:
                            logger.error(f"Failed to write debug log: {e}")

                        # Pour éviter des durées négatives ou absurdes si last_update est vieux
                        if duration_seconds > 0:
                            updates["last_occupancy_duration_seconds"] = int(duration_seconds)
                            updates["last_occupancy_duration_minutes"] = duration_minutes  # Keep for compatibility
                            updates["last_occupancy_end_time"] = now
                            logger.info(f"Place {place_id}: Enregistrement durée occupation = {int(duration_seconds)}s ({duration_minutes}m)")
                        else:
                            logger.warning(f"Place {place_id}: Durée négative ou nulle ({duration_seconds}), pas d'enregistrement.")

                    updates["etat"] = "free"
                    updates["reserved_by"] = None
                    updates["reserved_by_email"] = None
                    updates["reservation_start_time"] = None
                    updates["reservation_end_time"] = None
                    transition = "reserved->free (sensor override)"
                    logger.info(f"Place {place_id}: Capteur détecte départ sur place réservée -> libération")
                elif current_etat == "free":
                    # Déjà libre, pas de changement mais on met à jour last_update
                    transition = "free->free (no change)"
            
            if updates:
                self.db.collection(self.COLLECTION_PLACES).document(place_id).update(updates)
            
            new_etat = updates.get("etat", current_etat)
            logger.info(f"Place {place_id}: {current_etat} -> {new_etat}")
            
            # Invalidate cache when place status changes
            if "etat" in updates:
                from database.firebase_cache import get_firebase_cache
                cache = get_firebase_cache()
                cache.invalidate("parking:all_places")
                logger.debug("Cache invalidated due to place status update")
            
            return {"etat": new_etat, "transition": transition}
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la place: {e}")
            raise
    
    async def reserve_place(
        self,
        place_id: str,
        user_id: str,
        user_email: str,
        duration_minutes: int,
        vehicle_plate: Optional[str] = None,
        phone: Optional[str] = None,
        payment_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Réserve une place de parking.
        Utilise une transaction Firestore pour éviter les conflits.
        """
        # Récupérer les paramètres avant la transaction
        settings = await self.get_system_settings()
        currency = settings.get("currency", "USD")
        
        # Déterminer le taux horaire
        if currency == "USD":
            hourly_rate = float(settings.get("hourly_rate_usd", settings.get("hourly_rate", 2)))
        else: # FC
            hourly_rate = float(settings.get("hourly_rate_fc", settings.get("hourly_rate", 1000)))
            
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
            
            reservation_id = f"RES-{place_id}-{int(now.timestamp())}"
            
            updates = {
                "etat": "reserved",
                "reserved_by": user_id,
                "reserved_by_email": user_email,
                "vehicle_plate": vehicle_plate,
                "reservation_id": reservation_id,
                "reservation_start_time": now,
                "reservation_end_time": end_time,
                "reservation_duration_minutes": duration_minutes,
                "currency": currency,
                "last_update": now
            }
            
            # Créer le paiement automatiquement avec le bon montant
            import uuid
            import math
            
            duration_hours = duration_minutes / 60.0
            raw_amount = duration_hours * hourly_rate
            
            if currency == "FC":
                amount = math.ceil(raw_amount)
            else:
                amount = round(raw_amount, 2)
                if amount < 0.1: amount = 0.1 # Minimum safe amount

            
            payment_id = f"PAY-AUTO-{uuid.uuid4().hex[:8]}"
            payment_ref = self.db.collection(self.COLLECTION_PAYMENTS).document(payment_id)
            
            # Utiliser les données utilisateur si dispos, sinon défauts réalistes
            res_phone = phone or "0990000000"
            res_method = payment_method or "MOBILE_MONEY"
            
            payment_data = {
                "payment_id": payment_id,
                "reservation_id": reservation_id,
                "place_id": place_id,
                "user_id": user_id,
                "user_email": user_email,
                "user_name": user_id, 
                "amount": amount,
                "currency": currency,
                "status": "success",
                "method": res_method,
                "phone": res_phone,         
                "phone_number": res_phone,
                "transaction_ref": f"TX-{uuid.uuid4().hex[:12].upper()}",
                "created_at": now,
                "updated_at": now
            }
            transaction.set(payment_ref, payment_data)
            
            transaction.update(place_ref, updates)
            
            return {**place_data, **updates, "auto_payment": payment_data}
        
        try:
            result = reserve_in_transaction(transaction)
            logger.info(f"Place {place_id} réservée pour {user_id} (avec paiement auto)")
            
            # Invalidate cache to ensure frontend shows updated status
            from database.firebase_cache import get_firebase_cache
            cache = get_firebase_cache()
            cache.invalidate("parking:all_places")
            logger.debug("Cache invalidated due to reservation")
            
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
                "access_code": None,
                "reservation_id": None,
                "last_update": datetime.utcnow()
            }
            
            # DEBUG: Lire l'état actuel
            doc_ref = self.db.collection(self.COLLECTION_PLACES).document(place_id)
            doc_snap = doc_ref.get()
            if doc_snap.exists:
                logger.info(f"État AVANT annulation pour {place_id}: {doc_snap.to_dict()}")
            else:
                logger.error(f"Place {place_id} introuvable avant annulation!")

            self.db.collection(self.COLLECTION_PLACES).document(place_id).update(updates)
            
            # DEBUG: Lire l'état après
            doc_snap_after = doc_ref.get()
            logger.info(f"État APRÈS annulation pour {place_id}: {doc_snap_after.to_dict()}")
            
            # Invalider le cache des places pour que l'admin voie le changement immédiatement
            try:
                from database.firebase_cache import get_firebase_cache
                cache = get_firebase_cache()
                cache.invalidate("parking:all_places")
                cache.invalidate(f"parking:place:{place_id}")
            except Exception as e:
                logger.error(f"Erreur invalidation cache: {e}")

            logger.info(f"Place {place_id} libérée")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la libération de la place {place_id}: {e}")
            raise
    
    async def delete_place(self, place_id: str) -> bool:
        """Supprime définitivement une place de parking."""
        try:
            self.db.collection(self.COLLECTION_PLACES).document(place_id).delete()
            
            # Invalider le cache
            try:
                from database.firebase_cache import get_firebase_cache
                cache = get_firebase_cache()
                cache.invalidate("parking:all_places")
                cache.invalidate(f"parking:place:{place_id}")
            except Exception:
                pass
                
            logger.info(f"Place {place_id} supprimée définitivement")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la place {place_id}: {e}")
            raise
    
    async def get_expired_reservations(self) -> List[Dict[str, Any]]:
        """Récupère les réservations expirées."""
        import asyncio
        
        def _get_expired_sync():
            """Synchronous helper to fetch expired reservations."""
            now = datetime.utcnow()
            
            places_ref = self.db.collection(self.COLLECTION_PLACES)
            # Fetch all reserved places to catch those without end_time (ghosts)
            query = places_ref.where(
                filter=FieldFilter("etat", "==", "reserved")
            )
            
            docs = query.stream()
            expired = []
            for doc in docs:
                data = doc.to_dict()
                data["place_id"] = doc.id
                
                end_time = data.get("reservation_end_time")
                
                if end_time:
                    # Normal expiry check
                    if hasattr(end_time, "timestamp"):
                        end_dt = datetime.fromtimestamp(end_time.timestamp())
                    else:
                        end_dt = end_time
                    
                    if end_dt < now:
                        expired.append(data)
                else:
                    # Ghost check: No end_time but etat is reserved. 
                    # If last_update is more than 10 mins ago, it's a ghost.
                    last_update = data.get("last_update")
                    if last_update:
                        if hasattr(last_update, "timestamp"):
                            update_dt = datetime.fromtimestamp(last_update.timestamp())
                        else:
                            update_dt = last_update
                        
                        if (now - update_dt).total_seconds() > 600: # 10 minutes
                            logger.warning(f"Ghost reservation detected for {doc.id}")
                            expired.append(data)
                    else:
                        # No update time? Ghost for sure.
                        expired.append(data)
            
            return expired
        
        try:
            # Run blocking Firestore query in thread pool
            expired = await asyncio.to_thread(_get_expired_sync)
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

    async def get_all_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupère tous les utilisateurs depuis Firestore."""
        try:
            users_ref = self.db.collection(self.COLLECTION_USERS)
            docs = users_ref.limit(limit).stream()
            users = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                # Convertir les timestamps
                for key in ["updated_at", "created_at"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                users.append(data)
            return users
        except Exception as e:
            logger.error(f"Erreur récupération tous utilisateurs: {e}")
            return []

    async def update_user_status(self, user_id: str, disabled: bool) -> bool:
        """Active ou désactive un utilisateur dans Firestore."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_USERS).document(user_id)
            doc_ref.update({
                "disabled": disabled,
                "updated_at": datetime.utcnow()
            })
            return True
        except Exception as e:
            logger.error(f"Erreur mise à jour statut utilisateur {user_id}: {e}")
            return False

    async def delete_user(self, user_id: str) -> bool:
        """Supprime un profil utilisateur de Firestore."""
        try:
            self.db.collection(self.COLLECTION_USERS).document(user_id).delete()
            return True
        except Exception as e:
            logger.error(f"Erreur suppression utilisateur {user_id}: {e}")
            return False
    
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
                data = doc.to_dict()
                data["place_id"] = doc.id
                
                # Convert timestamps to ISO for frontend
                for key in ["reservation_start_time", "reservation_end_time", "last_update"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                
                return data
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la réservation: {e}")
            raise
    
    
    # ==================== USER PROFILES ====================
    
    COLLECTION_USER_PROFILES = "users"
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Récupère le profil utilisateur depuis Firestore."""
        try:
            doc = self.db.collection(self.COLLECTION_USER_PROFILES).document(user_id).get()
            if doc.exists:
                return doc.to_dict()
            return {}
        except Exception as e:
            logger.error(f"Erreur récupération profil utilisateur {user_id}: {e}")
            return {}
    
    async def upsert_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour ou crée le profil utilisateur dans Firestore."""
        try:
            # Ajouter timestamp de mise à jour
            updates["updated_at"] = datetime.utcnow()
            
            # Merge pour ne pas écraser les autres champs (reservation_count, total_spent, etc.)
            self.db.collection(self.COLLECTION_USER_PROFILES).document(user_id).set(updates, merge=True)
            logger.info(f"Profil utilisateur {user_id} mis à jour: {updates}")
            return True
        except Exception as e:
            logger.error(f"Erreur mise à jour profil utilisateur {user_id}: {e}")
            return False
    
    # ==================== RESERVATIONS (Collection séparée) ====================
    
    COLLECTION_ACCESS_CODES = "access_codes"
    COLLECTION_PAYMENTS = "payments"
    COLLECTION_BARRIER_LOGS = "barrier_logs"
    COLLECTION_SETTINGS = "settings"
    
    async def get_system_settings(self) -> Dict[str, Any]:
        """Récupère les paramètres du système."""
        try:
            doc = self.db.collection(self.COLLECTION_SETTINGS).document("global").get()
            if doc.exists:
                return doc.to_dict()
            return {}
        except Exception as e:
            logger.error(f"Erreur récupération paramètres: {e}")
            return {}
            
    async def update_system_settings(self, settings_data: Dict[str, Any]) -> bool:
        """Met à jour les paramètres du système."""
        try:
            self.db.collection(self.COLLECTION_SETTINGS).document("global").set(settings_data, merge=True)
            return True
        except Exception as e:
            logger.error(f"Erreur mise à jour paramètres: {e}")
            return False
    
    async def get_all_reservations(
        self,
        status_filter: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Récupère toutes les réservations avec la structure attendue par le frontend."""
        try:
            # Récupérer toutes les places
            all_places = await self.get_all_places()
            
            # Récupérer les paramètres pour le taux horaire
            settings = await self.get_system_settings()
            currency = settings.get("currency", "USD")
            
            # Determine rate based on currency, prioritizing specific rates
            if currency == "USD":
                hourly_rate = settings.get("hourly_rate_usd", settings.get("hourly_rate", 2))
            else:
                hourly_rate = settings.get("hourly_rate_fc", settings.get("hourly_rate", 1000))
            
            reservations = []
            for p in all_places:
                etat = p.get("etat", "free")
                reserved_by = p.get("reserved_by")
                
                # Ignorer les places libres sans historique de réservation
                if not reserved_by and etat == "free":
                    continue
                
                # Calculer la durée et le montant
                duration_minutes = p.get("reservation_duration_minutes", 60)
                duration_hours = duration_minutes / 60
                amount = int(duration_hours * hourly_rate)
                
                # Mapper le statut de place (etat) vers le statut de réservation
                if etat == "reserved":
                    status = "active"
                elif etat == "occupied":
                    status = "active"
                elif etat == "free" and reserved_by:
                    # Place libérée = réservation terminée
                    status = "completed"
                else:
                    status = "cancelled"
                
                # Appliquer le filtre de statut
                if status_filter and status_filter != status:
                    continue
                
                # Récupérer le profil utilisateur complet pour avoir display_name et vehicle_plate
                user_email = p.get("reserved_by_email", "")
                user_name = user_email.split("@")[0] if user_email else "Utilisateur"
                vehicle_plate = None
                
                if reserved_by:
                    try:
                        user_profile = await self.get_user_profile(reserved_by)
                        if user_profile:
                            # Utiliser display_name si disponible, sinon utiliser email
                            user_name = user_profile.get("display_name") or user_profile.get("email") or user_email
                            # Récupérer la plaque d'immatriculation
                            vehicle_plate = user_profile.get("vehicle_plate")
                    except Exception as e:
                        logger.warning(f"Impossible de récupérer le profil utilisateur {reserved_by}: {e}")
                        # Garder les valeurs par défaut si erreur
                
                # Créer l'objet réservation avec tous les champs attendus par le frontend
                reservation = {
                    "id": p.get("place_id", ""),  # ID de la réservation = place_id
                    "place_id": p.get("place_id", ""),
                    "user_id": reserved_by,
                    "user_email": user_email,
                    "user_name": user_name,  # Nom complet maintenant!
                    "vehicle_plate": vehicle_plate,  # Plaque récupérée depuis le profil
                    "start_time": p.get("reservation_start_time"),
                    "created_at": p.get("reservation_start_time"),
                    "end_time": p.get("reservation_end_time"),
                    "duration": float(duration_hours), # Garder la précision float
                    "duration_minutes": duration_minutes, # Explicite
                    "reservation_duration_minutes": duration_minutes, # Pour être sûr
                    "amount": amount,
                    "status": status,
                    "access_code": None,  # Sera enrichi si nécessaire
                    # Garder aussi les champs originaux pour compatibilité
                    "etat": etat,
                    "reservation_end_time": p.get("reservation_end_time"),
                    "last_update": p.get("last_update")
                }
                
                # Convertir les timestamps en ISO strings si nécessaire
                for key in ["start_time", "created_at", "end_time", "reservation_end_time", "last_update"]:
                    if reservation.get(key) and hasattr(reservation[key], 'isoformat'):
                        reservation[key] = reservation[key].isoformat()
                
                reservations.append(reservation)
            
            # Trier par date de création (plus récent en premier)
            reservations.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
            
            # Limiter et retourner
            return reservations[:limit]
        except Exception as e:
            logger.error(f"Erreur récupération réservations: {e}")
            return []

    async def get_reservation(self, reservation_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une réservation par son ID ou l'ID de la place.
        Dans notre modèle actuel, les réservations sont stockées DANS les places.
        """
        try:
            # Cas 1: L'ID est un ID de place (ex: 'a1', 'P1', etc.)
            # Check simple sur la longueur pour deviner si c'est un ID de place (IDs courts)
            if len(reservation_id) <= 5:
                place = await self.get_place_by_id(reservation_id)
                if place and (place.get("etat") in ["reserved", "occupied"] or place.get("reserved_by")):
                    return {
                        "id": reservation_id,
                        "place_id": reservation_id,
                        "user_id": place.get("reserved_by"),
                        "status": "active" if place.get("etat") in ["reserved", "occupied"] else "completed",
                        "access_code": place.get("access_code"),
                        "start_time": place.get("reservation_start_time")
                    }
            
            # Cas 2: Recherche par ID de réservation (si stocké dans la place) ou scan complet
            # Note: C'est pas optimal mais avec 6 places ça va
            places = await self.get_all_places()
            for p in places:
                # Si on stocke un reservation_id spécifiquement
                if p.get("reservation_id") == reservation_id:
                    return {
                        "id": reservation_id,
                        "place_id": p.get("id"),
                        "user_id": p.get("reserved_by"),
                        "status": "active",
                        "access_code": p.get("access_code")
                    }
                    
            return None
        except Exception as e:
            logger.error(f"Erreur get_reservation: {e}")
            return None

    async def cancel_reservation(self, reservation_id: str) -> bool:
        """
        Annule une réservation.
        Si reservation_id est un ID de place, libère la place.
        """
        try:
            logger.info(f"Annulation de la réservation/place {reservation_id}")
            
            # Si c'est un ID de place (ex 'a3'), on libère directement
            if len(reservation_id) <= 3 and reservation_id.lower().startswith('a'):
                success = await self.release_place(reservation_id)
                return success
            
            # Sinon on cherche la place associée
            res = await self.get_reservation(reservation_id)
            if res and res.get("place_id"):
                success = await self.release_place(res["place_id"])
                return success
                
            logger.warning(f"Impossible d'annuler: réservation {reservation_id} introuvable")
            return False
        except Exception as e:
            logger.error(f"Erreur annulation réservation: {e}")
            return False
    

    async def update_reservation_status(self, reservation_id: str, status: str) -> bool:
        """Met à jour le statut d'une réservation."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_PLACES).document(reservation_id)
            doc_ref.update({
                "reservation_status": status,
                "status_updated_at": datetime.utcnow().isoformat()
            })
            logger.info(f"Statut de la réservation {reservation_id} mis à jour: {status}")
            
            # Invalider le cache car le statut a changé
            try:
                from database.firebase_cache import get_firebase_cache
                cache = get_firebase_cache()
                cache.invalidate("parking:all_places")
                cache.invalidate(f"parking:place:{reservation_id}")
            except Exception:
                pass
                
            return True
        except Exception as e:
            logger.error(f"Erreur mise à jour statut réservation {reservation_id}: {e}")
            return False
    
    # ==================== ACCESS CODES ====================
    
    async def save_access_code(self, code_data: Dict[str, Any]) -> str:
        """Sauvegarde un code d'accès."""
        try:
            code = code_data["code"]
            self.db.collection(self.COLLECTION_ACCESS_CODES).document(code).set(code_data)
            logger.info(f"Code d'accès {code} sauvegardé")
            return code
        except Exception as e:
            logger.error(f"Erreur sauvegarde code d'accès: {e}")
            raise
    
    async def get_access_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Récupère un code d'accès."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_ACCESS_CODES).document(code)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Erreur récupération code: {e}")
            return None
    
    async def update_access_code(self, code: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un code d'accès."""
        try:
            self.db.collection(self.COLLECTION_ACCESS_CODES).document(code).update(updates)
            return True
        except Exception as e:
            logger.error(f"Erreur mise à jour code: {e}")
            return False
    
    async def get_all_access_codes(
        self,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Récupère tous les codes d'accès."""
        try:
            codes_ref = self.db.collection(self.COLLECTION_ACCESS_CODES)
            
            if status_filter:
                query = codes_ref.where(
                    filter=FieldFilter("status", "==", status_filter)
                )
            else:
                query = codes_ref
            
            docs = query.stream()
            codes = []
            for doc in docs:
                data = doc.to_dict()
                # Convertir les timestamps
                for key in ["created_at", "expires_at", "used_at"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                codes.append(data)
            return codes
        except Exception as e:
            logger.error(f"Erreur récupération codes: {e}")
            return []
    
    async def delete_access_code(self, code: str) -> bool:
        """Supprime un code d'accès."""
        try:
            self.db.collection(self.COLLECTION_ACCESS_CODES).document(code).delete()
            return True
        except Exception as e:
            logger.error(f"Erreur suppression code: {e}")
            return False
    
    # ==================== PAYMENTS ====================
    
    async def save_payment(self, payment_data: Dict[str, Any]) -> str:
        """Sauvegarde un paiement."""
        try:
            payment_id = payment_data.get("payment_id")
            if not payment_id:
                # Générer un ID si non fourni
                import uuid
                payment_id = str(uuid.uuid4())
                payment_data["payment_id"] = payment_id
            
            self.db.collection(self.COLLECTION_PAYMENTS).document(payment_id).set(payment_data)
            logger.info(f"Paiement {payment_id} sauvegardé")
            return payment_id
        except Exception as e:
            logger.error(f"Erreur sauvegarde paiement: {e}")
            raise
    
    async def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un paiement."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_PAYMENTS).document(payment_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                for key in ["created_at", "updated_at"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                return data
            return None
        except Exception as e:
            logger.error(f"Erreur récupération paiement: {e}")
            return None
    
    async def update_payment(self, payment_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un paiement."""
        try:
            self.db.collection(self.COLLECTION_PAYMENTS).document(payment_id).update(updates)
            return True
        except Exception as e:
            logger.error(f"Erreur mise à jour paiement: {e}")
            return False
    
    async def get_all_payments(
        self,
        status_filter: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Récupère tous les paiements."""
        try:
            payments_ref = self.db.collection(self.COLLECTION_PAYMENTS)
            
            if status_filter:
                query = payments_ref.where(
                    filter=FieldFilter("status", "==", status_filter)
                ).limit(limit)
            else:
                query = payments_ref.limit(limit)
            
            docs = query.stream()
            payments = []
            for doc in docs:
                data = doc.to_dict()
                for key in ["created_at", "updated_at"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                payments.append(data)
            return payments
        except Exception as e:
            logger.error(f"Erreur récupération paiements: {e}")
            return []
    
    async def get_payments_by_reservation(self, reservation_id: str) -> List[Dict[str, Any]]:
        """Récupère les paiements d'une réservation."""
        try:
            payments_ref = self.db.collection(self.COLLECTION_PAYMENTS)
            query = payments_ref.where(
                filter=FieldFilter("reservation_id", "==", reservation_id)
            )
            
            docs = query.stream()
            payments = []
            for doc in docs:
                data = doc.to_dict()
                for key in ["created_at", "updated_at"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                payments.append(data)
            return payments
        except Exception as e:
            logger.error(f"Erreur récupération paiements réservation: {e}")
            return []
    
    # ==================== BARRIER LOGS ====================
    
    async def log_barrier_action(self, log_data: Dict[str, Any]) -> str:
        """Enregistre une action de barrière."""
        try:
            import uuid
            log_id = str(uuid.uuid4())
            log_data["log_id"] = log_id
            log_data["timestamp"] = datetime.utcnow()
            
            self.db.collection(self.COLLECTION_BARRIER_LOGS).document(log_id).set(log_data)
            return log_id
        except Exception as e:
            logger.error(f"Erreur log barrière: {e}")
            raise
    
    async def get_barrier_logs(
        self,
        barrier_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Récupère les logs de barrière."""
        try:
            logs_ref = self.db.collection(self.COLLECTION_BARRIER_LOGS)
            
            if barrier_id:
                query = logs_ref.where(
                    filter=FieldFilter("barrier_id", "==", barrier_id)
                ).limit(limit)
            else:
                query = logs_ref.limit(limit)
            
            docs = query.stream()
            logs = []
            for doc in docs:
                data = doc.to_dict()
                if data.get("timestamp") and hasattr(data["timestamp"], 'isoformat'):
                    data["timestamp"] = data["timestamp"].isoformat()
                logs.append(data)
                
            # Trier par timestamp (décroissant) en Python
            logs.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)
            
            return logs
        except Exception as e:
            logger.error(f"Erreur récupération logs: {e}")
            return []


    async def reset_system_data(self, keep_admin_email: Optional[str] = None) -> Dict[str, int]:
        """
        Réinitialise toutes les données du système (réservations, paiements, utilisateurs).
        Garde l'admin spécifié et les places (mais les remet à zéro).
        """
        try:
            stats = {"users": 0, "reservations": 0, "payments": 0, "places_reset": 0}
            logger.info("Démarrage réinitialisation système...")

            # 1. Supprimer Réservations & Logs Barrière
            # On utilise des batchs séparés pour éviter les limites de taille et s'assurer que ça passe
            
            # --- Réservations ---
            batch = self.db.batch()
            count = 0
            docs = self.db.collection(self.COLLECTION_RESERVATIONS).stream()
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            if count > 0:
                batch.commit()
            stats["reservations"] = count
            logger.info(f"Réservations supprimées: {count}")

            # --- Paiements ---
            batch = self.db.batch()
            count = 0
            docs = self.db.collection(self.COLLECTION_PAYMENTS).stream()
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            if count > 0:
                batch.commit()
            stats["payments"] = count
            logger.info(f"Paiements supprimés: {count}")
            
            # --- Codes d'accès ---
            batch = self.db.batch()
            count = 0
            docs = self.db.collection(self.COLLECTION_ACCESS_CODES).stream()
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            if count > 0:
                batch.commit()
            logger.info(f"Codes accès supprimés: {count}")

            # --- Logs Barrière ---
            batch = self.db.batch()
            count = 0
            docs = self.db.collection(self.COLLECTION_BARRIER_LOGS).stream()
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            if count > 0:
                batch.commit()
            logger.info(f"Logs barrière supprimés: {count}")

            # --- Réinitialiser Places (update) ---
            batch = self.db.batch()
            count = 0
            docs = self.db.collection(self.COLLECTION_PLACES).stream()
            for doc in docs:
                updates = {
                    "etat": "free",
                    "reserved_by": None,
                    "reserved_by_email": None,
                    "reservation_start_time": None,
                    "reservation_end_time": None,
                    "reservation_duration_minutes": None,
                    "access_code": None,
                    "reservation_id": None,
                    "vehicle_plate": None,
                    "last_update": datetime.utcnow()
                }
                batch.update(doc.reference, updates)
                count += 1
                stats["places_reset"] += 1
                check_count = 0 # Not used here, fixed logic
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            if count > 0:
                batch.commit()
            logger.info(f"Places réinitialisées: {stats['places_reset']}")

            # --- Supprimer Utilisateurs (sauf l'admin courant) ---
            batch = self.db.batch()
            count = 0
            docs = self.db.collection(self.COLLECTION_USERS).stream()
            for doc in docs:
                data = doc.to_dict()
                email = data.get("email")
                # On garde l'admin actuel et le compte "admin" par défaut s'il existe
                if email != keep_admin_email and email != "admin@aeropark.com":
                    batch.delete(doc.reference)
                    stats["users"] += 1
                    count += 1
                    if count >= 400:
                        batch.commit()
                        batch = self.db.batch()
                        count = 0
            if count > 0:
                batch.commit()
            logger.info(f"Utilisateurs supprimés: {stats['users']}")
                
            # Invalider caches
            try:
                from database.firebase_cache import get_firebase_cache
                cache = get_firebase_cache()
                cache.invalidate("parking:all_places")
            except:
                pass

            return stats
            
        except Exception as e:
            logger.error(f"Erreur reset système: {e}")
            raise

# Instance singleton
_db_instance: Optional[FirebaseDB] = None


def get_db() -> FirebaseDB:
    """Obtient l'instance singleton de FirebaseDB."""
    global _db_instance
    if _db_instance is None:
        _db_instance = FirebaseDB()
    return _db_instance
