import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Mêmes imports que dans l'app
env_path = Path("backend/.env")
load_dotenv(env_path)

def test_init():
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")
    print(f"Key starts with: {private_key[:30] if private_key else 'None'}")
    print(f"Key ends with: {private_key[-30:] if private_key else 'None'}")
    
    # Simuler le fix de config.py
    formatted_key = private_key.replace("\\n", "\n")
    
    cred_dict = {
        "type": "service_account",
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": formatted_key,
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    }
    
    try:
        cred = credentials.Certificate(cred_dict)
        # Tenter une opération simple
        app = firebase_admin.initialize_app(cred, name="test_app")
        db = firestore.client(app=app)
        doc = db.collection("test").document("test").get()
        print("Success! Data fetched.")
    except Exception as e:
        print(f"Failure: {e}")

if __name__ == "__main__":
    test_init()
