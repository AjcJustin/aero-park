import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
import logging

env_path = Path("backend/.env")
load_dotenv(env_path)

def test_key_loading():
    pk = os.getenv("FIREBASE_PRIVATE_KEY")
    if not pk:
        print("Error: No key in ENV")
        return

    # Process as in config.py
    pk = pk.strip()
    if (pk.startswith('"') and pk.endswith('"')) or (pk.startswith("'") and pk.endswith("'")):
        pk = pk[1:-1]
    pk = pk.strip().replace("\\n", "\n")
    
    try:
        # Tenter de charger en tant que clé privée RSA
        key = serialization.load_pem_private_key(
            pk.encode('ascii'),
            password=None
        )
        print("✅ SUCCESS: Key is a valid PEM RSA Private Key")
        print(f"Key Size: {key.key_size} bits")
    except Exception as e:
        print(f"❌ FAILURE: Key could not be loaded: {e}")
        # Print first few chars of cleaned pk to see markers
        print(f"Cleaned PK Start: {repr(pk[:50])}")

if __name__ == "__main__":
    test_key_loading()
