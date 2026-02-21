#!/usr/bin/env python3
"""
Script pour définir le rôle admin d'un utilisateur via Firebase Custom Claims
"""
import firebase_admin
from firebase_admin import auth, credentials
import os
import sys

# Ajouter le répertoire courant au path pour importer config
sys.path.append(os.path.dirname(__file__))
from config import get_settings

# Initialiser Firebase avec credentials depuis .env
try:
    firebase_admin.get_app()
except ValueError:
    try:
        settings = get_settings()
        cred_dict = settings.get_firebase_credentials()
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialisé avec succès via config.py")
    except Exception as e:
        print(f"❌ Erreur d'initialisation: {e}")
        exit(1)

# UID de l'utilisateur (trouvé dans les logs)
USER_UID = "0v6y7fUrbqe369mlGy9ZHxrRFlQ2"

try:
    # Définir les custom claims
    auth.set_custom_user_claims(USER_UID, {'role': 'admin'})
    print(f"✅ Rôle admin défini pour l'utilisateur {USER_UID}")
    
    # Vérifier
    user = auth.get_user(USER_UID)
    print(f"✅ Custom claims: {user.custom_claims}")
    print("\n🔹 IMPORTANT: Déconnectez-vous et reconnectez-vous pour que les changements prennent effet!")
    
except Exception as e:
    print(f"❌ Erreur: {e}")
