"""
AeroPark Smart System - Firebase Database Module
Handles all Firebase Firestore operations for parking management.
"""

import firebase_admin
from firebase_admin import credentials, firestore, auth
from google.cloud.firestore_v1 import FieldFilter, Transaction
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
from functools import lru_cache
import logging

from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Global Firebase app instance
_firebase_app: Optional[firebase_admin.App] = None
_firestore_client = None


def init_firebase() -> firebase_admin.App:
    """
    Initialize Firebase Admin SDK.
    Should be called once at application startup.
    """
    global _firebase_app, _firestore_client
    
    if _firebase_app is not None:
        logger.info("Firebase already initialized")
        return _firebase_app
    
    try:
        settings = get_settings()
        cred = credentials.Certificate(settings.get_firebase_credentials())
        
        _firebase_app = firebase_admin.initialize_app(cred, {
            'databaseURL': settings.firebase_database_url
        })
        
        _firestore_client = firestore.client()
        logger.info("Firebase initialized successfully")
        
        return _firebase_app
        
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise


def get_firestore_client():
    """Get the Firestore client instance."""
    global _firestore_client
    if _firestore_client is None:
        init_firebase()
    return _firestore_client


class FirebaseDB:
    """
    Firebase Firestore database handler.
    Provides all CRUD operations for parking management.
    """
    
    COLLECTION_SPOTS = "parking_spots"
    COLLECTION_RESERVATIONS = "reservations"
    COLLECTION_USERS = "users"
    COLLECTION_SENSOR_LOGS = "sensor_logs"
    
    def __init__(self):
        self.db = get_firestore_client()
    
    # ==================== PARKING SPOTS ====================
    
    async def get_all_spots(self) -> List[Dict[str, Any]]:
        """Retrieve all parking spots."""
        try:
            spots_ref = self.db.collection(self.COLLECTION_SPOTS)
            docs = spots_ref.order_by("spot_number").stream()
            
            spots = []
            for doc in docs:
                spot_data = doc.to_dict()
                spot_data["id"] = doc.id
                spots.append(spot_data)
            
            return spots
        except Exception as e:
            logger.error(f"Error fetching spots: {e}")
            raise
    
    async def get_spot_by_id(self, spot_id: str) -> Optional[Dict[str, Any]]:
        """Get a single parking spot by ID."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_SPOTS).document(spot_id)
            doc = doc_ref.get()
            
            if doc.exists:
                spot_data = doc.to_dict()
                spot_data["id"] = doc.id
                return spot_data
            return None
        except Exception as e:
            logger.error(f"Error fetching spot {spot_id}: {e}")
            raise
    
    async def get_spot_by_sensor_id(self, sensor_id: str) -> Optional[Dict[str, Any]]:
        """Get parking spot by associated sensor ID."""
        try:
            spots_ref = self.db.collection(self.COLLECTION_SPOTS)
            query = spots_ref.where(filter=FieldFilter("sensor_id", "==", sensor_id)).limit(1)
            docs = query.stream()
            
            for doc in docs:
                spot_data = doc.to_dict()
                spot_data["id"] = doc.id
                return spot_data
            return None
        except Exception as e:
            logger.error(f"Error fetching spot by sensor {sensor_id}: {e}")
            raise
    
    async def create_spot(self, spot_data: Dict[str, Any]) -> str:
        """Create a new parking spot."""
        try:
            spot_data["created_at"] = datetime.utcnow()
            spot_data["updated_at"] = datetime.utcnow()
            spot_data["status"] = "AVAILABLE"
            
            doc_ref = self.db.collection(self.COLLECTION_SPOTS).document()
            doc_ref.set(spot_data)
            
            logger.info(f"Created parking spot: {doc_ref.id}")
            return doc_ref.id
        except Exception as e:
            logger.error(f"Error creating spot: {e}")
            raise
    
    async def update_spot(self, spot_id: str, updates: Dict[str, Any]) -> bool:
        """Update a parking spot."""
        try:
            updates["updated_at"] = datetime.utcnow()
            
            doc_ref = self.db.collection(self.COLLECTION_SPOTS).document(spot_id)
            doc_ref.update(updates)
            
            logger.info(f"Updated parking spot: {spot_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating spot {spot_id}: {e}")
            raise
    
    async def delete_spot(self, spot_id: str) -> bool:
        """Delete a parking spot."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_SPOTS).document(spot_id)
            doc_ref.delete()
            
            logger.info(f"Deleted parking spot: {spot_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting spot {spot_id}: {e}")
            raise
    
    async def reserve_spot_transaction(
        self,
        spot_id: str,
        user_id: str,
        user_email: str,
        duration_minutes: int
    ) -> Dict[str, Any]:
        """
        Reserve a parking spot using a Firestore transaction.
        Ensures atomic operation to prevent race conditions.
        """
        transaction = self.db.transaction()
        spot_ref = self.db.collection(self.COLLECTION_SPOTS).document(spot_id)
        
        @firestore.transactional
        def reserve_in_transaction(transaction: Transaction) -> Dict[str, Any]:
            # Read the current spot data
            spot_doc = spot_ref.get(transaction=transaction)
            
            if not spot_doc.exists:
                raise ValueError("Parking spot not found")
            
            spot_data = spot_doc.to_dict()
            
            # Check if spot is available
            if spot_data.get("status") != "AVAILABLE":
                raise ValueError(f"Spot is not available. Current status: {spot_data.get('status')}")
            
            # Calculate reservation times
            now = datetime.utcnow()
            end_time = now + timedelta(minutes=duration_minutes)
            
            # Update spot with reservation
            updates = {
                "status": "RESERVED",
                "reserved_by": user_id,
                "reserved_by_email": user_email,
                "reservation_start_time": now,
                "reservation_end_time": end_time,
                "reservation_duration_minutes": duration_minutes,
                "updated_at": now
            }
            
            transaction.update(spot_ref, updates)
            
            # Create reservation record
            reservation_ref = self.db.collection(self.COLLECTION_RESERVATIONS).document()
            reservation_data = {
                "id": reservation_ref.id,
                "spot_id": spot_id,
                "user_id": user_id,
                "user_email": user_email,
                "start_time": now,
                "end_time": end_time,
                "duration_minutes": duration_minutes,
                "status": "active",
                "created_at": now
            }
            transaction.set(reservation_ref, reservation_data)
            
            # Return updated spot data
            updated_spot = {**spot_data, **updates, "id": spot_id}
            return {
                "spot": updated_spot,
                "reservation_id": reservation_ref.id
            }
        
        try:
            result = reserve_in_transaction(transaction)
            logger.info(f"Reserved spot {spot_id} for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Transaction failed for spot {spot_id}: {e}")
            raise
    
    async def release_spot(self, spot_id: str, reason: str = None) -> bool:
        """Release a parking spot back to available status."""
        try:
            updates = {
                "status": "AVAILABLE",
                "reserved_by": None,
                "reserved_by_email": None,
                "reservation_start_time": None,
                "reservation_end_time": None,
                "reservation_duration_minutes": None,
                "occupied_at": None,
                "updated_at": datetime.utcnow()
            }
            
            await self.update_spot(spot_id, updates)
            
            # Log the release
            if reason:
                logger.info(f"Released spot {spot_id}: {reason}")
            
            return True
        except Exception as e:
            logger.error(f"Error releasing spot {spot_id}: {e}")
            raise
    
    async def update_spot_from_sensor(
        self,
        spot_id: str,
        is_occupied: bool,
        sensor_id: str = None
    ) -> Dict[str, Any]:
        """
        Update spot status based on sensor reading.
        Handles the RESERVED → OCCUPIED and OCCUPIED → AVAILABLE transitions.
        """
        try:
            spot = await self.get_spot_by_id(spot_id)
            if not spot:
                raise ValueError(f"Spot {spot_id} not found")
            
            current_status = spot.get("status")
            now = datetime.utcnow()
            
            # Log sensor reading
            log_ref = self.db.collection(self.COLLECTION_SENSOR_LOGS).document()
            log_ref.set({
                "spot_id": spot_id,
                "sensor_id": sensor_id,
                "is_occupied": is_occupied,
                "previous_status": current_status,
                "timestamp": now
            })
            
            if is_occupied:
                # Vehicle detected
                if current_status == "RESERVED":
                    # Reserved spot now occupied - vehicle arrived
                    updates = {
                        "status": "OCCUPIED",
                        "occupied_at": now,
                        "updated_at": now
                    }
                    await self.update_spot(spot_id, updates)
                    return {"status": "OCCUPIED", "transition": "RESERVED->OCCUPIED"}
                    
                elif current_status == "AVAILABLE":
                    # Unreserved spot now occupied (walk-in or unauthorized)
                    updates = {
                        "status": "OCCUPIED",
                        "occupied_at": now,
                        "updated_at": now
                    }
                    await self.update_spot(spot_id, updates)
                    return {"status": "OCCUPIED", "transition": "AVAILABLE->OCCUPIED"}
                    
                else:
                    # Already occupied, no change needed
                    return {"status": "OCCUPIED", "transition": None}
            else:
                # No vehicle detected
                if current_status == "OCCUPIED":
                    # Vehicle left - return to available
                    await self.release_spot(spot_id, "Vehicle departed (sensor)")
                    return {"status": "AVAILABLE", "transition": "OCCUPIED->AVAILABLE"}
                else:
                    # No change needed
                    return {"status": current_status, "transition": None}
                    
        except Exception as e:
            logger.error(f"Error updating spot from sensor: {e}")
            raise
    
    async def get_expired_reservations(self) -> List[Dict[str, Any]]:
        """Get all reservations that have expired."""
        try:
            now = datetime.utcnow()
            
            spots_ref = self.db.collection(self.COLLECTION_SPOTS)
            query = spots_ref.where(
                filter=FieldFilter("status", "==", "RESERVED")
            ).where(
                filter=FieldFilter("reservation_end_time", "<", now)
            )
            
            docs = query.stream()
            expired = []
            for doc in docs:
                spot_data = doc.to_dict()
                spot_data["id"] = doc.id
                expired.append(spot_data)
            
            return expired
        except Exception as e:
            logger.error(f"Error fetching expired reservations: {e}")
            raise
    
    # ==================== USERS ====================
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile from Firestore."""
        try:
            doc_ref = self.db.collection(self.COLLECTION_USERS).document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            raise
    
    async def upsert_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """Create or update user profile."""
        try:
            profile_data["updated_at"] = datetime.utcnow()
            
            doc_ref = self.db.collection(self.COLLECTION_USERS).document(user_id)
            doc_ref.set(profile_data, merge=True)
            
            return True
        except Exception as e:
            logger.error(f"Error upserting user {user_id}: {e}")
            raise
    
    async def get_user_active_reservation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's current active reservation."""
        try:
            spots_ref = self.db.collection(self.COLLECTION_SPOTS)
            query = spots_ref.where(
                filter=FieldFilter("reserved_by", "==", user_id)
            ).where(
                filter=FieldFilter("status", "in", ["RESERVED", "OCCUPIED"])
            ).limit(1)
            
            docs = query.stream()
            for doc in docs:
                spot_data = doc.to_dict()
                spot_data["id"] = doc.id
                return spot_data
            return None
        except Exception as e:
            logger.error(f"Error fetching user reservation: {e}")
            raise
    
    # ==================== INITIALIZATION ====================
    
    async def initialize_default_spots(self, count: int = 5) -> List[str]:
        """
        Initialize default parking spots if none exist.
        Called on application startup.
        """
        try:
            existing = await self.get_all_spots()
            if existing:
                logger.info(f"Found {len(existing)} existing spots, skipping initialization")
                return []
            
            created_ids = []
            zones = ["Terminal 1", "Terminal 1", "Terminal 2", "Terminal 2", "VIP"]
            
            for i in range(1, count + 1):
                spot_data = {
                    "spot_number": f"A{i}",
                    "zone": zones[i - 1] if i <= len(zones) else "General",
                    "floor": 1,
                    "sensor_id": f"ESP32-SENSOR-{i:03d}"
                }
                spot_id = await self.create_spot(spot_data)
                created_ids.append(spot_id)
            
            logger.info(f"Initialized {count} default parking spots")
            return created_ids
            
        except Exception as e:
            logger.error(f"Error initializing default spots: {e}")
            raise


# Create a singleton instance
_db_instance: Optional[FirebaseDB] = None


def get_db() -> FirebaseDB:
    """Get the FirebaseDB singleton instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = FirebaseDB()
    return _db_instance
