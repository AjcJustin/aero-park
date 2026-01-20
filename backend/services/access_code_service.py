"""
AeroPark Smart System - Access Code Service
Génération et validation des codes d'accès 3 caractères.
"""

import random
import string
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from database.firebase_db import get_db

logger = logging.getLogger(__name__)


class AccessCodeService:
    """Service de gestion des codes d'accès."""
    
    COLLECTION_CODES = "access_codes"
    CODE_LENGTH = 3
    CODE_CHARS = string.ascii_uppercase + string.digits  # A-Z, 0-9
    
    def __init__(self):
        self.db = get_db()
    
    def generate_unique_code(self) -> str:
        """
        Génère un code unique de 3 caractères alphanumériques.
        Ex: A7F, K2P, B9X
        """
        return ''.join(random.choices(self.CODE_CHARS, k=self.CODE_LENGTH))
    
    async def create_access_code(
        self,
        user_id: str,
        user_email: str,
        place_id: str,
        reservation_id: str,
        expires_at: datetime
    ) -> str:
        """
        Crée un nouveau code d'accès unique pour une réservation.
        
        Args:
            user_id: UID Firebase de l'utilisateur
            user_email: Email de l'utilisateur
            place_id: ID de la place réservée
            reservation_id: ID de la réservation
            expires_at: Date d'expiration du code
            
        Returns:
            str: Le code d'accès généré (3 caractères)
        """
        # Générer un code unique
        max_attempts = 100
        for _ in range(max_attempts):
            code = self.generate_unique_code()
            
            # Vérifier que le code n'existe pas déjà (actif)
            existing = await self.get_active_code(code)
            if existing is None:
                break
        else:
            raise Exception("Impossible de générer un code unique")
        
        # Créer le document du code
        code_data = {
            "code": code,
            "user_id": user_id,
            "user_email": user_email,
            "place_id": place_id,
            "reservation_id": reservation_id,
            "status": "active",
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "used_at": None
        }
        
        # Sauvegarder dans Firestore
        self.db.db.collection(self.COLLECTION_CODES).document(code).set(code_data)
        
        logger.info(f"Code d'accès créé: {code} pour place {place_id}, utilisateur {user_email}")
        
        return code
    
    async def get_active_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Récupère un code actif par son ID."""
        try:
            doc = self.db.db.collection(self.COLLECTION_CODES).document(code).get()
            
            if doc.exists:
                data = doc.to_dict()
                if data.get("status") == "active":
                    return data
            return None
        except Exception as e:
            logger.error(f"Erreur récupération code {code}: {e}")
            return None
    
    async def validate_code(
        self,
        code: str,
        sensor_presence: bool = True
    ) -> Dict[str, Any]:
        """
        Valide un code d'accès.
        
        Conditions de validation:
        1. Le code existe
        2. Le code est actif (pas utilisé, pas expiré)
        3. Le capteur de présence détecte un véhicule
        4. Le code n'a pas expiré
        
        Args:
            code: Code à valider (3 caractères)
            sensor_presence: État du capteur de présence
            
        Returns:
            Dict avec access_granted et détails
        """
        code = code.upper().strip()
        
        # Vérifier la présence du véhicule
        if not sensor_presence:
            return {
                "access_granted": False,
                "message": "Aucun véhicule détecté à la barrière",
                "place_id": None
            }
        
        # Récupérer le code
        code_data = await self.get_active_code(code)
        
        if code_data is None:
            logger.warning(f"Code invalide ou inexistant: {code}")
            return {
                "access_granted": False,
                "message": "Code d'accès invalide",
                "place_id": None
            }
        
        # Vérifier l'expiration
        expires_at = code_data.get("expires_at")
        if expires_at:
            # Convertir le timestamp Firestore si nécessaire
            if hasattr(expires_at, 'timestamp'):
                expires_at = datetime.fromtimestamp(expires_at.timestamp())
            
            if datetime.utcnow() > expires_at:
                # Marquer comme expiré
                await self.invalidate_code(code, "expired")
                return {
                    "access_granted": False,
                    "message": "Code d'accès expiré",
                    "place_id": code_data.get("place_id")
                }
        
        # Calculer le temps restant
        remaining_minutes = None
        if expires_at:
            remaining = expires_at - datetime.utcnow()
            remaining_minutes = max(0, int(remaining.total_seconds() / 60))
        
        # Code valide - le marquer comme utilisé
        await self.mark_code_used(code)
        
        logger.info(f"Code {code} validé avec succès pour place {code_data.get('place_id')}")
        
        return {
            "access_granted": True,
            "message": "Accès autorisé",
            "place_id": code_data.get("place_id"),
            "user_email": code_data.get("user_email"),
            "remaining_time_minutes": remaining_minutes
        }
    
    async def mark_code_used(self, code: str) -> bool:
        """Marque un code comme utilisé."""
        try:
            self.db.db.collection(self.COLLECTION_CODES).document(code).update({
                "status": "used",
                "used_at": datetime.utcnow()
            })
            logger.info(f"Code {code} marqué comme utilisé")
            return True
        except Exception as e:
            logger.error(f"Erreur marquage code {code}: {e}")
            return False
    
    async def invalidate_code(self, code: str, reason: str = "cancelled") -> Dict[str, Any]:
        """
        Invalide un code d'accès.
        
        Args:
            code: Code à invalider
            reason: Raison (expired, cancelled, admin)
        
        Returns:
            Dict avec success et message
        """
        try:
            doc = self.db.db.collection(self.COLLECTION_CODES).document(code).get()
            if not doc.exists:
                return {
                    "success": False,
                    "message": f"Code {code} non trouvé"
                }
            
            self.db.db.collection(self.COLLECTION_CODES).document(code).update({
                "status": reason,
                "invalidated_at": datetime.utcnow()
            })
            logger.info(f"Code {code} invalidé: {reason}")
            return {
                "success": True,
                "message": f"Code {code} invalidé avec succès"
            }
        except Exception as e:
            logger.error(f"Erreur invalidation code {code}: {e}")
            return {
                "success": False,
                "message": f"Erreur: {str(e)}"
            }
    
    async def get_all_codes(
        self,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Récupère tous les codes avec filtre optionnel."""
        try:
            collection = self.db.db.collection(self.COLLECTION_CODES)
            
            if status_filter:
                query = collection.where("status", "==", status_filter)
            else:
                query = collection
            
            docs = query.stream()
            
            codes = []
            for doc in docs:
                data = doc.to_dict()
                # Convertir les timestamps pour la sérialisation JSON
                for key in ["created_at", "expires_at", "used_at", "invalidated_at"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                codes.append(data)
            return codes
        except Exception as e:
            logger.error(f"Erreur récupération codes: {e}")
            return []
    
    async def cleanup_expired_codes(self) -> Dict[str, Any]:
        """Nettoie les codes expirés (tâche planifiée)."""
        try:
            now = datetime.utcnow()
            docs = self.db.db.collection(self.COLLECTION_CODES)\
                .where("status", "==", "active")\
                .where("expires_at", "<", now).stream()
            
            count = 0
            for doc in docs:
                await self.invalidate_code(doc.id, "expired")
                count += 1
            
            if count > 0:
                logger.info(f"{count} codes expirés nettoyés")
            
            return {
                "success": True,
                "cleaned_count": count
            }
        except Exception as e:
            logger.error(f"Erreur nettoyage codes: {e}")
            return {
                "success": False,
                "cleaned_count": 0
            }


# Instance singleton
_access_code_service: Optional[AccessCodeService] = None


def get_access_code_service() -> AccessCodeService:
    """Obtient l'instance singleton du service."""
    global _access_code_service
    if _access_code_service is None:
        _access_code_service = AccessCodeService()
    return _access_code_service

# Export singleton instance for easy import
access_code_service = get_access_code_service()