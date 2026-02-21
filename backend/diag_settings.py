
import asyncio
from database.firebase_db import get_db

async def check_settings():
    db = get_db()
    settings = await db.get_system_settings()
    print("--- RAW SETTINGS ---")
    for k, v in settings.items():
        print(f"{k}: {v}")
    
    print("\n--- DERIVED LOGIC ---")
    currency = settings.get("currency", "USD")
    print(f"Currency: {currency}")
    
    rate_generic = settings.get("hourly_rate")
    print(f"Generic hourly_rate: {rate_generic}")
    
    rate_fc = settings.get("hourly_rate_fc")
    print(f"hourly_rate_fc: {rate_fc}")
    
    rate_usd = settings.get("hourly_rate_usd")
    print(f"hourly_rate_usd: {rate_usd}")
    
    # Current logic
    final_rate = settings.get("hourly_rate", settings.get("hourly_rate_usd" if currency == "USD" else "hourly_rate_fc", 2 if currency == "USD" else 1000))
    print(f"Computed Rate (Current Logic): {final_rate}")

    # Proposed logic
    proposed_rate = settings.get("hourly_rate_usd" if currency == "USD" else "hourly_rate_fc")
    if proposed_rate is None:
        proposed_rate = settings.get("hourly_rate", 2 if currency == "USD" else 1000)
    print(f"Computed Rate (Proposed Logic): {proposed_rate}")

if __name__ == "__main__":
    asyncio.run(check_settings())
