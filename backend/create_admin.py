"""
Script pour créer un compte administrateur dans Firebase.
Exécuter ce script une seule fois pour créer l'admin.

Usage:
    cd backend
    python create_admin.py
"""

import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration Admin
ADMIN_EMAIL = "abrahamfaith325@gmail.com"
ADMIN_PASSWORD = "aeropark"
ADMIN_NAME = "Abraham Faith"


def create_admin_with_firebase_admin():
    """Créer l'admin avec Firebase Admin SDK."""
    try:
        import firebase_admin
        from firebase_admin import credentials, auth
        
        # Initialiser Firebase si pas encore fait
        if not firebase_admin._apps:
            # Chercher le fichier de credentials
            cred_file = None
            for file in os.listdir('.'):
                if file.endswith('.json') and 'firebase' in file.lower():
                    cred_file = file
                    break
            
            if not cred_file:
                print("❌ Fichier de credentials Firebase non trouvé!")
                return False
            
            cred = credentials.Certificate(cred_file)
            firebase_admin.initialize_app(cred)
            print(f"✅ Firebase initialisé avec: {cred_file}")
        
        # Vérifier si l'utilisateur existe déjà
        try:
            existing_user = auth.get_user_by_email(ADMIN_EMAIL)
            print(f"⚠️  L'utilisateur {ADMIN_EMAIL} existe déjà!")
            print(f"   UID: {existing_user.uid}")
            print(f"   Email: {existing_user.email}")
            
            # Mettre à jour le nom si nécessaire
            auth.update_user(
                existing_user.uid,
                display_name=ADMIN_NAME
            )
            print(f"✅ Nom mis à jour: {ADMIN_NAME}")
            
            # Définir les custom claims pour admin
            auth.set_custom_user_claims(existing_user.uid, {"role": "admin"})
            print("✅ Claims admin définis!")
            
            return True
            
        except auth.UserNotFoundError:
            # Créer le nouvel utilisateur admin
            user = auth.create_user(
                email=ADMIN_EMAIL,
                password=ADMIN_PASSWORD,
                display_name=ADMIN_NAME,
                email_verified=True
            )
            
            print(f"✅ Utilisateur admin créé!")
            print(f"   UID: {user.uid}")
            print(f"   Email: {user.email}")
            print(f"   Nom: {ADMIN_NAME}")
            
            # Définir les custom claims pour admin
            auth.set_custom_user_claims(user.uid, {"role": "admin"})
            print("✅ Claims admin définis!")
            
            return True
            
    except ImportError:
        print("❌ Firebase Admin SDK non installé. Installez avec: pip install firebase-admin")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def main():
    print("=" * 50)
    print("   CRÉATION COMPTE ADMIN AEROPARK")
    print("=" * 50)
    print()
    print(f"📧 Email: {ADMIN_EMAIL}")
    print(f"🔑 Mot de passe: {ADMIN_PASSWORD}")
    print(f"👤 Nom: {ADMIN_NAME}")
    print()
    
    success = create_admin_with_firebase_admin()
    
    print()
    print("=" * 50)
    
    if success:
        print("✅ ADMIN CRÉÉ AVEC SUCCÈS!")
        print()
        print("🔐 Pour vous connecter:")
        print(f"   Email: {ADMIN_EMAIL}")
        print(f"   Mot de passe: {ADMIN_PASSWORD}")
        print()
        print("🌐 Page de connexion admin:")
        print("   http://localhost:5500/frontend/pages/admin-login.html")
    else:
        print("❌ Échec de la création de l'admin")
    
    print("=" * 50)


if __name__ == "__main__":
    main()
