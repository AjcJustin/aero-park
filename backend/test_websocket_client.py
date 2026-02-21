"""
AeroPark - WebSocket Test Client
Outil de diagnostic pour tester les messages WebSocket en temps réel
"""

import asyncio
import websockets
import json
from datetime import datetime
import sys

class WebSocketTestClient:
    def __init__(self, uri="ws://localhost:8000/ws/parking"):
        self.uri = uri
        self.message_count = 0
        
    async def connect_and_listen(self):
        """Se connecte au WebSocket et écoute les messages."""
        print(f"🔌 Connexion à {self.uri}...")
        print("=" * 80)
        
        try:
            async with websockets.connect(self.uri) as websocket:
                print(f"✅ Connecté avec succès!")
                print(f"⏰ Début de l'écoute à {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 80)
                print()
                
                # Écouter les messages
                async for message in websocket:
                    self.message_count += 1
                    await self.handle_message(message)
                    
        except websockets.exceptions.WebSocketException as e:
            print(f"❌ Erreur WebSocket: {e}")
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    async def handle_message(self, message):
        """Traite et affiche un message reçu."""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            print(f"📨 Message #{self.message_count} [{timestamp}]")
            print(f"   Type: {msg_type}")
            
            # Afficher les informations clés selon le type
            if msg_type == "status_update":
                self.display_status_update(data)
            elif msg_type == "reservation":
                self.display_reservation(data)
            elif msg_type == "connected":
                print(f"   Message: {data.get('message', 'N/A')}")
            else:
                print(f"   Données: {json.dumps(data, indent=6, ensure_ascii=False)}")
            
            print("-" * 80)
            print()
            
        except json.JSONDecodeError:
            print(f"⚠️  Message non-JSON reçu: {message}")
            print("-" * 80)
            print()
    
    def display_status_update(self, data):
        """Affiche un message de mise à jour de statut."""
        # Vérifier toutes les variantes de clés
        free = data.get("libres") or data.get("free") or data.get("free_spots") or data.get("available", "?")
        total = data.get("total_places") or data.get("total") or data.get("total_spots", "?")
        occupied = data.get("occupees") or data.get("occupied") or data.get("occupied_spots", "?")
        reserved = data.get("reservees") or data.get("reserved") or data.get("reserved_spots", "?")
        
        print(f"   📊 STATUT PARKING:")
        print(f"      🟢 Libres:    {free}/{total}")
        print(f"      🔴 Occupées:  {occupied}")
        print(f"      🟡 Réservées: {reserved}")
        
        # Vérifier la présence de toutes les clés attendues
        expected_keys = ["libres", "free", "free_spots", "available", "total_places", "total", "total_spots"]
        present_keys = [k for k in expected_keys if k in data]
        
        print(f"   🔑 Clés présentes: {', '.join(present_keys)}")
        
        # Vérifier si le tableau places est présent
        if "places" in data:
            places_count = len(data["places"]) if isinstance(data["places"], list) else 0
            print(f"   📍 Tableau places: {places_count} éléments")
        else:
            print(f"   📍 Tableau places: ABSENT (version lite)")
        
        # Taille du message
        msg_size = len(json.dumps(data))
        print(f"   📦 Taille JSON: {msg_size} octets")
        
        if msg_size > 2048:
            print(f"   ⚠️  ATTENTION: Message volumineux (>{msg_size} octets) - risque de crash ESP32")
    
    def display_reservation(self, data):
        """Affiche un message de réservation."""
        donnees = data.get("donnees", {})
        place_id = donnees.get("place_id", "?")
        action = donnees.get("action", "?")
        
        action_emoji = "🟢" if action in ["create", "reserve"] else "🔴"
        action_text = "RÉSERVATION" if action in ["create", "reserve"] else "ANNULATION"
        
        print(f"   {action_emoji} {action_text}")
        print(f"      Place: {place_id}")
        print(f"      Action: {action}")

async def main():
    """Point d'entrée principal."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "AEROPARK - TEST CLIENT WEBSOCKET" + " " * 26 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Permettre de spécifier l'URI en argument
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/ws/parking"
    
    client = WebSocketTestClient(uri)
    
    print("💡 Instructions:")
    print("   - Laissez ce client tourner")
    print("   - Faites une réservation depuis le frontend ou l'API")
    print("   - Observez les messages qui arrivent en temps réel")
    print("   - Appuyez sur Ctrl+C pour arrêter")
    print()
    
    try:
        await client.connect_and_listen()
    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print(f"🛑 Arrêt du client. Total de messages reçus: {client.message_count}")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
