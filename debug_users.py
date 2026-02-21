import asyncio
import sys
import os
from pprint import pprint

# Ajouter le dossier backend au path pour trouver les modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.firebase_db import get_db

async def debug_data():
    try:
        db = get_db()
        print("--- USERS ---")
        users = db.db.collection(db.COLLECTION_USERS).stream()
        for u in users:
            data = u.to_dict()
            print(f"User: {data.get('email')} | Name: {data.get('name')} | Phone: {data.get('phone')} / {data.get('phone_number')}")

        print("\n--- PLACES (RESERVATIONS) ---")
        places = await db.get_all_places()
        reserved = [p for p in places if p.get("etat") == "reserved"]
        for p in reserved:
            print(f"Place {p.get('place_id')} reserved by {p.get('reserved_by')} ({p.get('reserved_by_email')})")
            print(f"   Duration: {p.get('reservation_duration_minutes')} min")
            print(f"   Start: {p.get('reservation_start_time')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_data())
