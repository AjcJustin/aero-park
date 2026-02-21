"""
Script pour donner les droits admin à un utilisateur existant.

Usage:
    cd backend
    python grant_admin.py <user_id>

Exemple:
    python grant_admin.py 0v6y7fUrbqe369mlGy9ZHxrRFlQ2
"""

import sys
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()


def grant_admin_rights(user_id: str):
    """Donne les droits admin à un utilisateur existant."""
    try:
        import firebase_admin
        from firebase_admin import credentials, auth, firestore
        
        # Initialiser Firebase si pas encore fait
        if not firebase_admin._apps:
            # Chercher le fichier de credentials
            cred_file = None
            search_dirs = ['.', '..']  # Chercher dans le dossier courant et parent
            
            for search_dir in search_dirs:
                if cred_file:
                    break
                try:
                    for file in os.listdir(search_dir):
                        if file.endswith('.json') and 'firebase' in file.lower():
                            cred_file = os.path.join(search_dir, file)
                            break
                except:
                    continue
            
            if not cred_file:
                print("❌ Fichier de credentials Firebase non trouvé!")
                print("   Recherché dans: . et ..")
                return False
            
            cred = credentials.Certificate(cred_file)
            firebase_admin.initialize_app(cred)
            print(f"✅ Firebase initialisé avec: {cred_file}")
        
        # Vérifier si l'utilisateur existe
        try:
            user = auth.get_user(user_id)
            print(f"\n📧 Utilisateur trouvé:")
            print(f"   UID: {user.uid}")
            print(f"   Email: {user.email}")
            print(f"   Nom: {user.display_name or 'Non défini'}")
            print()
            
        except auth.UserNotFoundError:
            print(f"❌ Utilisateur {user_id} non trouvé dans Firebase Auth!")
            return False
        
        # Mettre à jour le profil dans Firestore
        db = firestore.client()
        user_ref = db.collection("users").document(user_id)
        
        user_ref.set({
            "uid": user_id,
            "email": user.email,
            "display_name": user.display_name,
            "role": "admin",  # IMPORTANT!
            "email_verified": user.email_verified,
        }, merge=True)
        
        print("✅ Profil Firestore mis à jour avec role='admin'")
        
        # Optionnel: Définir aussi les custom claims
        auth.set_custom_user_claims(user_id, {"role": "admin"})
        print("✅ Custom claims définis")
        
        print()
        print("=" * 60)
        print("✅ DROITS ADMIN ACCORDÉS AVEC SUCCÈS!")
        print("=" * 60)
        print()
        print("⚠️  IMPORTANT:")
        print("   L'utilisateur doit SE DÉCONNECTER et SE RECONNECTER")
        print("   pour que les changements prennent effet.")
        print()
        print("🔄 Étapes à suivre:")
        print("   1. Déconnectez-vous de l'admin panel")
        print("   2. Reconnectez-vous avec ce compte")
        print("   3. Les droits admin seront actifs")
        print()
        
        return True
        
    except ImportError:
        print("❌ Firebase Admin SDK non installé. Installez avec: pip install firebase-admin")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("   ACCORDER DROITS ADMIN - AEROPARK")
    print("=" * 60)
    print()
    
    if len(sys.argv) < 2:
        print("❌ Usage: python grant_admin.py <user_id>")
        print()
        print("Exemple:")
        print("   python grant_admin.py 0v6y7fUrbqe369mlGy9ZHxrRFlQ2")
        print()
        print("💡 Vous pouvez trouver le user_id dans les logs du serveur")
        print("   ou en vous connectant et en regardant le token.")
        return
    
    user_id = sys.argv[1]
    print(f"🎯 Utilisateur cible: {user_id}")
    print()
    
    grant_admin_rights(user_id)


if __name__ == "__main__":
    main()
