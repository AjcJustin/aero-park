"""
AeroPark Smart System - Payment Simulation Service
Simulation de paiement pour réservation de parking.
"""

import uuid
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from database.firebase_db import get_db
from services.access_code_service import get_access_code_service
from models.payment import PaymentStatus, PaymentMethod, MobileMoneyProvider, PricingInfo

logger = logging.getLogger(__name__)


class PaymentService:
    """Service de simulation de paiement."""
    
    COLLECTION_PAYMENTS = "payments"
    
    def __init__(self):
        self.db = get_db()
        self.pricing = PricingInfo()
    
    def generate_payment_id(self) -> str:
        """Génère un ID unique pour le paiement."""
        return f"PAY-{uuid.uuid4().hex[:12].upper()}"
    
    def generate_transaction_ref(self) -> str:
        """Génère une référence de transaction simulée."""
        return f"TXN-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    async def simulate_payment(
        self,
        user_id: str,
        user_email: str,
        place_id: str,
        duration_minutes: int,
        method: PaymentMethod = PaymentMethod.CARD,
        simulate_failure: bool = False
    ) -> Dict[str, Any]:
        """
        Simule un paiement et crée une réservation si réussi.
        
        Args:
            user_id: UID Firebase de l'utilisateur
            user_email: Email de l'utilisateur
            place_id: ID de la place à réserver
            duration_minutes: Durée de la réservation
            method: Méthode de paiement
            simulate_failure: Forcer un échec pour test
            
        Returns:
            Dict avec résultat du paiement et réservation
        """
        payment_id = self.generate_payment_id()
        amount = self.pricing.calculate_price(duration_minutes)
        
        # Vérifier que la place est disponible
        place = await self.db.get_place_by_id(place_id)
        if not place:
            return {
                "success": False,
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED,
                "message": f"Place {place_id} introuvable",
                "amount": amount,
                "reservation_confirmed": False
            }
        
        if place.get("etat") != "free":
            return {
                "success": False,
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED,
                "message": f"Place {place_id} non disponible (état: {place.get('etat')})",
                "amount": amount,
                "reservation_confirmed": False
            }
        
        # Simuler le traitement du paiement
        payment_success = not simulate_failure
        
        # Simulation: 5% de chance d'échec aléatoire en production
        if not simulate_failure and random.random() < 0.05:
            payment_success = False
        
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=duration_minutes)
        
        if payment_success:
            # Paiement réussi - créer la réservation
            reservation_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
            
            # Créer le code d'accès
            access_service = get_access_code_service()
            access_code = await access_service.create_access_code(
                user_id=user_id,
                user_email=user_email,
                place_id=place_id,
                reservation_id=reservation_id,
                expires_at=expires_at
            )
            
            # Mettre à jour la place comme réservée
            await self.db.reserve_place(
                place_id=place_id,
                user_id=user_id,
                user_email=user_email,
                duration_minutes=duration_minutes
            )
            
            # Enregistrer le paiement
            payment_data = {
                "payment_id": payment_id,
                "user_id": user_id,
                "user_email": user_email,
                "reservation_id": reservation_id,
                "place_id": place_id,
                "amount": amount,
                "currency": self.pricing.currency,
                "method": method.value,
                "status": PaymentStatus.SUCCESS.value,
                "duration_minutes": duration_minutes,
                "created_at": now,
                "completed_at": now,
                "transaction_ref": self.generate_transaction_ref(),
                "access_code": access_code
            }
            
            self.db.db.collection(self.COLLECTION_PAYMENTS).document(payment_id).set(payment_data)
            
            logger.info(f"Paiement {payment_id} réussi pour place {place_id}, code: {access_code}")
            
            return {
                "success": True,
                "payment_id": payment_id,
                "status": PaymentStatus.SUCCESS,
                "message": "Paiement accepté, réservation confirmée",
                "amount": amount,
                "currency": self.pricing.currency,
                "transaction_ref": payment_data["transaction_ref"],
                "reservation_confirmed": True,
                "access_code": access_code,
                "place_id": place_id,
                "expires_at": expires_at
            }
        else:
            # Paiement échoué
            payment_data = {
                "payment_id": payment_id,
                "user_id": user_id,
                "user_email": user_email,
                "place_id": place_id,
                "amount": amount,
                "currency": self.pricing.currency,
                "method": method.value,
                "status": PaymentStatus.FAILED.value,
                "duration_minutes": duration_minutes,
                "created_at": now,
                "failure_reason": "Transaction refusée par le processeur" if simulate_failure else "Erreur réseau"
            }
            
            self.db.db.collection(self.COLLECTION_PAYMENTS).document(payment_id).set(payment_data)
            
            logger.warning(f"Paiement {payment_id} échoué pour place {place_id}")
            
            return {
                "success": False,
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED,
                "message": payment_data["failure_reason"],
                "amount": amount,
                "currency": self.pricing.currency,
                "reservation_confirmed": False
            }
    
    async def get_payment_by_id(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un paiement par son ID."""
        try:
            doc = self.db.db.collection(self.COLLECTION_PAYMENTS).document(payment_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Erreur récupération paiement {payment_id}: {e}")
            return None
    
    async def get_user_payments(self, user_id: str) -> List[Dict[str, Any]]:
        """Récupère tous les paiements d'un utilisateur."""
        try:
            docs = self.db.db.collection(self.COLLECTION_PAYMENTS)\
                .where("user_id", "==", user_id)\
                .order_by("created_at", direction="DESCENDING")\
                .limit(50).stream()
            
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Erreur récupération paiements utilisateur {user_id}: {e}")
            return []
    
    async def get_all_payments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupère tous les paiements (admin)."""
        try:
            docs = self.db.db.collection(self.COLLECTION_PAYMENTS)\
                .order_by("created_at", direction="DESCENDING")\
                .limit(limit).stream()
            
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Erreur récupération paiements: {e}")
            return []
    
    async def refund_payment(self, payment_id: str, reason: str = "admin_refund") -> Dict[str, Any]:
        """Simule un remboursement."""
        try:
            payment = await self.get_payment_by_id(payment_id)
            if not payment:
                return {
                    "success": False,
                    "payment_id": payment_id,
                    "message": "Paiement non trouvé"
                }
            
            if payment.get("status") != PaymentStatus.SUCCESS.value:
                return {
                    "success": False,
                    "payment_id": payment_id,
                    "message": f"Impossible de rembourser un paiement avec statut: {payment.get('status')}"
                }
            
            # Invalider le code d'accès si existant
            access_code = payment.get("access_code")
            if access_code:
                access_service = get_access_code_service()
                await access_service.invalidate_code(access_code, "refunded")
            
            # Libérer la place
            place_id = payment.get("place_id")
            if place_id:
                await self.db.release_place(place_id)
            
            refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
            
            # Mettre à jour le paiement
            self.db.db.collection(self.COLLECTION_PAYMENTS).document(payment_id).update({
                "status": PaymentStatus.REFUNDED.value,
                "refunded_at": datetime.utcnow(),
                "refund_reason": reason,
                "refund_id": refund_id
            })
            
            logger.info(f"Paiement {payment_id} remboursé: {reason}")
            
            return {
                "success": True,
                "payment_id": payment_id,
                "refund_id": refund_id,
                "amount_refunded": payment.get("amount", 0),
                "message": "Remboursement effectué avec succès"
            }
        except Exception as e:
            logger.error(f"Erreur remboursement {payment_id}: {e}")
            return {
                "success": False,
                "payment_id": payment_id,
                "message": f"Erreur lors du remboursement: {str(e)}"
            }
    
    async def get_pricing_info(self) -> Dict[str, Any]:
        """Retourne les informations de tarification."""
        return {
            "hourly_rate": self.pricing.base_rate_per_hour,
            "daily_max": self.pricing.daily_max,
            "first_minutes_free": self.pricing.first_minutes_free,
            "currency": self.pricing.currency,
            "currency_symbol": self.pricing.currency_symbol,
            "minimum_duration_minutes": self.pricing.minimum_duration_minutes,
            "maximum_duration_minutes": self.pricing.maximum_duration_minutes
        }
    
    async def calculate_amount(self, hours: float) -> float:
        """Calcule le montant pour une durée donnée."""
        # 15 premières minutes gratuites
        if hours <= 0.25:
            return 0.0
        billable_hours = hours - 0.25
        return round(billable_hours * self.pricing.base_rate_per_hour, 2)
    
    async def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un paiement par son ID."""
        return await self.get_payment_by_id(payment_id)
    
    async def get_payments_for_reservation(self, reservation_id: str) -> List[Dict[str, Any]]:
        """Récupère les paiements pour une réservation."""
        try:
            docs = self.db.db.collection(self.COLLECTION_PAYMENTS)\
                .where("reservation_id", "==", reservation_id)\
                .stream()
            
            payments = []
            for doc in docs:
                data = doc.to_dict()
                # Convertir les timestamps
                for key in ["created_at", "completed_at", "refunded_at"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                payments.append(data)
            return payments
        except Exception as e:
            logger.error(f"Erreur récupération paiements réservation {reservation_id}: {e}")
            return []
    
    async def get_all_payments(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Récupère tous les paiements (admin)."""
        try:
            collection = self.db.db.collection(self.COLLECTION_PAYMENTS)
            
            if status_filter:
                query = collection.where("status", "==", status_filter).limit(limit)
            else:
                query = collection.limit(limit)
            
            docs = query.stream()
            
            payments = []
            for doc in docs:
                data = doc.to_dict()
                # Convertir les timestamps
                for key in ["created_at", "completed_at", "refunded_at"]:
                    if data.get(key) and hasattr(data[key], 'isoformat'):
                        data[key] = data[key].isoformat()
                payments.append(data)
            return payments
        except Exception as e:
            logger.error(f"Erreur récupération paiements: {e}")
            return []
    
    # ========== MOBILE MONEY SIMULATION ==========
    
    def _mask_phone_number(self, phone: str) -> str:
        """Masque un numéro de téléphone (ex: ****1234)."""
        if len(phone) <= 4:
            return "*" * len(phone)
        return "*" * (len(phone) - 4) + phone[-4:]
    
    async def simulate_mobile_money_payment(
        self,
        provider: MobileMoneyProvider,
        phone_number: str,
        amount: float,
        reservation_id: str,
        user_id: str,
        user_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Simule un paiement Mobile Money (Orange Money, Airtel Money, M-Pesa).
        
        La réservation doit être en état PENDING_PAYMENT.
        - 80% de chance de succès
        - 20% de chance d'échec
        
        Si succès: Réservation passe à CONFIRMED, code d'accès généré
        Si échec: Réservation annulée, place libérée
        """
        payment_id = self.generate_payment_id()
        now = datetime.utcnow()
        phone_masked = self._mask_phone_number(phone_number)
        
        # Récupérer la réservation
        reservation = await self.db.get_reservation(reservation_id)
        if not reservation:
            return {
                "success": False,
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED,
                "message": f"Réservation {reservation_id} introuvable",
                "provider": provider,
                "phone_number_masked": phone_masked
            }
        
        # Vérifier que la réservation est en attente de paiement
        reservation_status = reservation.get("status", "pending_payment")
        if reservation_status not in ["pending_payment", "pending"]:
            return {
                "success": False,
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED,
                "message": f"Réservation déjà traitée (statut: {reservation_status})",
                "provider": provider,
                "phone_number_masked": phone_masked
            }
        
        place_id = reservation.get("place_id")
        
        # Simuler le traitement Mobile Money
        # 80% de chance de succès
        payment_success = random.random() < 0.80
        
        if payment_success:
            # Paiement réussi
            transaction_ref = self.generate_transaction_ref()
            
            # Calculer l'expiration (utiliser duration_minutes de la réservation ou 60 min par défaut)
            duration_minutes = reservation.get("duration_minutes", 60)
            expires_at = now + timedelta(minutes=duration_minutes)
            
            # Créer le code d'accès
            access_service = get_access_code_service()
            access_code = await access_service.create_access_code(
                user_id=user_id,
                user_email=user_email or reservation.get("user_email", ""),
                place_id=place_id,
                reservation_id=reservation_id,
                expires_at=expires_at
            )
            
            # Mettre à jour la réservation comme confirmée
            await self.db.update_reservation_status(reservation_id, "confirmed")
            
            # Enregistrer le paiement
            payment_data = {
                "payment_id": payment_id,
                "user_id": user_id,
                "user_email": user_email,
                "reservation_id": reservation_id,
                "place_id": place_id,
                "amount": amount,
                "currency": self.pricing.currency,
                "method": PaymentMethod.MOBILE.value,
                "provider": provider.value,
                "phone_number": phone_number,
                "phone_number_masked": phone_masked,
                "status": PaymentStatus.SUCCESS.value,
                "created_at": now,
                "completed_at": now,
                "transaction_ref": transaction_ref,
                "access_code": access_code
            }
            
            self.db.db.collection(self.COLLECTION_PAYMENTS).document(payment_id).set(payment_data)
            
            logger.info(
                f"Mobile Money {provider.value} paiement {payment_id} réussi | "
                f"Tel: {phone_masked} | Montant: {amount} | Code: {access_code}"
            )
            
            return {
                "success": True,
                "payment_id": payment_id,
                "status": PaymentStatus.SUCCESS,
                "message": f"Paiement {provider.value} accepté",
                "provider": provider,
                "phone_number_masked": phone_masked,
                "amount": amount,
                "currency": self.pricing.currency,
                "transaction_ref": transaction_ref,
                "reservation_status": "CONFIRMED",
                "access_code": access_code,
                "timestamp": now
            }
        else:
            # Paiement échoué
            failure_reasons = [
                "Solde insuffisant",
                "Transaction rejetée par l'opérateur",
                "Délai d'attente dépassé",
                "Numéro de téléphone non éligible",
                "Service temporairement indisponible"
            ]
            failure_reason = random.choice(failure_reasons)
            
            # Annuler la réservation
            await self.db.update_reservation_status(reservation_id, "cancelled")
            
            # Libérer la place
            if place_id:
                await self.db.release_place(place_id)
            
            # Enregistrer le paiement échoué
            payment_data = {
                "payment_id": payment_id,
                "user_id": user_id,
                "user_email": user_email,
                "reservation_id": reservation_id,
                "place_id": place_id,
                "amount": amount,
                "currency": self.pricing.currency,
                "method": PaymentMethod.MOBILE.value,
                "provider": provider.value,
                "phone_number": phone_number,
                "phone_number_masked": phone_masked,
                "status": PaymentStatus.FAILED.value,
                "created_at": now,
                "failure_reason": failure_reason
            }
            
            self.db.db.collection(self.COLLECTION_PAYMENTS).document(payment_id).set(payment_data)
            
            logger.warning(
                f"Mobile Money {provider.value} paiement {payment_id} échoué | "
                f"Tel: {phone_masked} | Raison: {failure_reason}"
            )
            
            return {
                "success": False,
                "payment_id": payment_id,
                "status": PaymentStatus.FAILED,
                "message": failure_reason,
                "provider": provider,
                "phone_number_masked": phone_masked,
                "amount": amount,
                "currency": self.pricing.currency,
                "reservation_status": "CANCELLED",
                "access_code": None,
                "timestamp": now
            }


# Instance singleton
_payment_service: Optional[PaymentService] = None


def get_payment_service() -> PaymentService:
    """Obtient l'instance singleton du service."""
    global _payment_service
    if _payment_service is None:
        _payment_service = PaymentService()
    return _payment_service
