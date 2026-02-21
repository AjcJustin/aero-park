import asyncio
import uuid
import random
import sys
import os

# Ajouter le dossier backend au path pour trouver les modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from datetime import datetime
from database.firebase_db import get_db

async def seed_payments():
    try:
        db = get_db()
        # 1. Récupérer toutes les places réservées
        places = await db.get_all_places()
        reserved_places = [p for p in places if p.get("etat") == "reserved"]
        
        print(f"Trouvé {len(reserved_places)} places réservées.")
        
        created_count = 0
        
        for p in reserved_places:
            place_id = p.get("place_id")
            # Vérifier si un paiement existe déjà pour cette résa
            # On simule un paiement pour chaque place réservée qui n'a pas de preuve
            
            user_id = p.get("reserved_by", "unknown_user")
            duration_minutes = p.get("reservation_duration_minutes", 60)
            
            # Calcul montant (simulé: 1h = 2$)
            amount = 2.0 * (duration_minutes / 60)
            if amount < 1: amount = 1.0
            
            payment_id = f"PAY-SEED-{uuid.uuid4().hex[:8]}"
            
            payment_data = {
                "payment_id": payment_id,
                "reservation_id": p.get("reservation_id", f"RES-{place_id}"),
                "place_id": place_id,
                "user_id": user_id,
                "user_email": p.get("reserved_by_email", "user@example.com"),
                "amount": round(amount, 2),
                "currency": "USD",
                "status": "success",
                "method": random.choice(["ORANGE_MONEY", "AIRTEL_MONEY", "MPESA"]),
                "phone_number": "0990000000",
                "transaction_ref": f"TX-{uuid.uuid4().hex[:12].upper()}",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Sauvegarder direct dans la collection payments (synchrone ici)
            db.db.collection(db.COLLECTION_PAYMENTS).document(payment_id).set(payment_data)
            created_count += 1
            print(f"Paiement créé pour place {place_id}: {amount}$")

        print(f"Terminé : {created_count} paiements générés.")
        
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    asyncio.run(seed_payments())
