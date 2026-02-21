import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Mêmes imports que dans l'app
env_path = Path("backend/.env")
load_dotenv(env_path)

def clean(s: str) -> str:
    if not s: return s
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    return s.strip()

def test_init():
    cred_dict = {
        "type": "service_account",
        "project_id": clean(os.getenv("FIREBASE_PROJECT_ID")),
        "private_key_id": clean(os.getenv("FIREBASE_PRIVATE_KEY_ID")),
        "private_key": clean(os.getenv("FIREBASE_PRIVATE_KEY")).replace("\\n", "\n"),
        "client_email": clean(os.getenv("FIREBASE_CLIENT_EMAIL")),
        "client_id": clean(os.getenv("FIREBASE_CLIENT_ID")),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    
    try:
        cred = credentials.Certificate(cred_dict)
        # Tenter une opération simple
        # On utilise un nom d'app unique pour éviter les conflits si déjà init
        try:
            app = firebase_admin.get_app("test_app_clean")
        except ValueError:
            app = firebase_admin.initialize_app(cred, name="test_app_clean")
            
        db = firestore.client(app=app)
        doc = db.collection("parking_places").limit(1).get()
        print("✅ SUCCESS: Successfully authenticated and fetched data!")
    except Exception as e:
        print(f"❌ FAILURE: {e}")

if __name__ == "__main__":
    test_init()
