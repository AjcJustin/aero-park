import sys
import os
import asyncio
import logging
from datetime import datetime

# Add empty directory to sys.path to allow imports from backend
sys.path.append(os.getcwd())

from database.firebase_db import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_transitions")

async def test_transitions():
    try:
        db = get_db()
        place_id = "P1"
        
        # 1. Check initial state
        logger.info(f"--- Checking initial state for {place_id} ---")
        
        # List all places to debug
        places_ref = db.db.collection(db.COLLECTION_PLACES)
        docs = places_ref.stream()
        all_ids = [d.id for d in docs]
        logger.info(f"Available places in DB: {all_ids}")

        doc = db.db.collection(db.COLLECTION_PLACES).document(place_id).get()
        if not doc.exists:
             logger.error(f"Place {place_id} does not exist! Available: {all_ids}")
             # Try first available if P1 missing
             if all_ids:
                 place_id = all_ids[0]
                 logger.info(f"Switching to place {place_id}")
                 doc = db.db.collection(db.COLLECTION_PLACES).document(place_id).get()
             else:
                 return
        
        place = doc.to_dict()
        current_etat = place.get("etat", "unknown")
        logger.info(f"Initial State: {current_etat}")
        logger.info(f"Initial Duration: {place.get('last_occupancy_duration_minutes', 'Not Set')}")
        
        # 2. Force Occupied (simulate arrival)
        logger.info(f"--- Forcing Occupied ---")
        await db.update_place_status(place_id, "occupied", force_signal=1)
        
        # Check update
        doc = db.db.collection(db.COLLECTION_PLACES).document(place_id).get()
        place = doc.to_dict()
        logger.info(f"State after Occupied: {place.get('etat')}")
        logger.info(f"Last Update: {place.get('last_update')}")
        
        # Wait a bit to have a duration > 0 (wait 2 seconds)
        logger.info("Waiting 2 seconds...")
        await asyncio.sleep(2)
        
        # 3. Force Free (simulate departure)
        logger.info(f"--- Forcing Free ---")
        await db.update_place_status(place_id, "free", force_signal=1)
        
        # 4. Check Final Result
        doc = db.db.collection(db.COLLECTION_PLACES).document(place_id).get()
        place = doc.to_dict()
        logger.info(f"State after Free: {place.get('etat')}")
        final_duration = place.get('last_occupancy_duration_minutes', 'MISSING')
        logger.info(f"FINAL DURATION: {final_duration}")
        
        if final_duration != 'MISSING' and int(final_duration) >= 0:
            logger.info("SUCCESS: Duration recorded!")
        else:
            logger.error("FAILURE: Duration NOT recorded.")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_transitions())
