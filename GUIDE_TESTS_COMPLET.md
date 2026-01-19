# 🧪 Guide de Tests Complet - AeroPark Smart System

## 📋 Prérequis
- Serveur démarré : `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
- URL Backend : `http://localhost:8000`
- Documentation Swagger : `http://localhost:8000/docs`

---

# PHASE 1 : Tests Backend (API REST)

## 1.1 Health Check
**Endpoint:** `GET /health`

**Résultat attendu:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-19T15:40:00.000Z",
  "version": "1.0.0"
}
```

---

## 1.2 Statut du Parking
**Endpoint:** `GET /api/v1/sensor/status`  
**Header:** `X-API-Key: aeropark-sensor-key-2024`

**Résultat attendu:**
```json
{
  "total_places": 6,
  "libres": 6,
  "occupees": 0,
  "reservees": 0,
  "places": [
    {"place_id": "a1", "etat": "free", "last_update": "..."},
    {"place_id": "a2", "etat": "free", "last_update": "..."},
    {"place_id": "a3", "etat": "free", "last_update": "..."},
    {"place_id": "a4", "etat": "free", "last_update": "..."},
    {"place_id": "a5", "etat": "free", "last_update": "..."},
    {"place_id": "a6", "etat": "free", "last_update": "..."}
  ]
}
```

---

## 1.3 Mise à jour Capteur (Simuler ESP32)
**Endpoint:** `POST /api/v1/sensor/update`  
**Header:** `X-API-Key: aeropark-sensor-key-2024`  
**Content-Type:** `application/json`

**Corps de la requête (place occupée):**
```json
{
  "place_id": "a1",
  "etat": "occupied",
  "force_signal": -65
}
```

**Résultat attendu:**
```json
{
  "success": true,
  "place_id": "a1",
  "new_etat": "occupied",
  "message": "État mis à jour avec succès"
}
```

**Corps de la requête (place libre):**
```json
{
  "place_id": "a1",
  "etat": "free",
  "force_signal": -65
}
```

**Résultat attendu:**
```json
{
  "success": true,
  "place_id": "a1",
  "new_etat": "free",
  "message": "État mis à jour avec succès"
}
```

---

## 1.4 Test Clé API Invalide
**Endpoint:** `GET /api/v1/sensor/status`  
**Header:** `X-API-Key: mauvaise-cle`

**Résultat attendu (401 Unauthorized):**
```json
{
  "detail": "Clé API invalide"
}
```

---

## 1.5 Test Sans Clé API
**Endpoint:** `GET /api/v1/sensor/status`  
**Aucun header X-API-Key**

**Résultat attendu (401 Unauthorized):**
```json
{
  "detail": "Clé API manquante. Ajoutez l'en-tête 'X-API-Key'."
}
```

---

## 1.6 Health Check Capteur
**Endpoint:** `GET /api/v1/sensor/health`  
**Header:** `X-API-Key: aeropark-sensor-key-2024`

**Résultat attendu:**
```json
{
  "status": "ok",
  "message": "Connexion capteur validée",
  "server_time": "2026-01-19T15:40:00.000Z"
}
```

---

# PHASE 2 : Tests WebSocket

## 2.1 Connexion WebSocket
**URL:** `ws://localhost:8000/ws/parking`

**À la connexion, vous recevez:**
```json
{
  "type": "connection_established",
  "message": "Connecté au système AeroPark",
  "timestamp": "2026-01-19T15:40:00.000Z"
}
```

## 2.2 Mise à jour en temps réel
Quand un capteur envoie une mise à jour, tous les clients WebSocket reçoivent:
```json
{
  "type": "place_update",
  "place_id": "a1",
  "etat": "occupied",
  "timestamp": "2026-01-19T15:40:00.000Z"
}
```

---

# PHASE 3 : Tests ESP32

## 3.1 Configuration ESP32

### Fichier `aeropark_sensor.ino` - Variables à configurer:
```cpp
// WiFi
const char* ssid = "VOTRE_WIFI";           // Nom de votre réseau WiFi
const char* password = "VOTRE_MOT_DE_PASSE"; // Mot de passe WiFi

// Serveur Backend
const char* serverUrl = "http://VOTRE_IP:8000";  // IP de votre PC
// Exemple: "http://192.168.1.100:8000"

// Clé API (NE PAS CHANGER)
const char* apiKey = "aeropark-sensor-key-2024";
```

### Pour trouver l'IP de votre PC:
```powershell
ipconfig | findstr "IPv4"
# Exemple résultat: 192.168.1.100
```

---

## 3.2 Branchements ESP32

| Composant | Pin ESP32 | Description |
|-----------|-----------|-------------|
| IR Sensor Place A1 | GPIO 13 | Détecteur infrarouge place 1 |
| IR Sensor Place A2 | GPIO 14 | Détecteur infrarouge place 2 |
| IR Sensor Place A3 | GPIO 25 | Détecteur infrarouge place 3 |
| IR Sensor Place A4 | GPIO 26 | Détecteur infrarouge place 4 |
| IR Sensor Place A5 | GPIO 27 | Détecteur infrarouge place 5 |
| IR Sensor Place A6 | GPIO 34 | Détecteur infrarouge place 6 |
| Servo Barrière | GPIO 4 | Contrôle de la barrière |
| IR Entrée | GPIO 32 | Détection véhicule entrée |
| IR Sortie | GPIO 33 | Détection véhicule sortie |
| LCD SDA | GPIO 21 | I2C Data |
| LCD SCL | GPIO 22 | I2C Clock |

---

## 3.3 Tests ESP32 - Comportements attendus

### Test A: Démarrage ESP32
**Action:** Allumer l'ESP32

**Attendu sur LCD:**
```
AeroPark System
Connexion WiFi...
```
Puis après connexion:
```
AeroPark Ready!
Libres: 6/6
```

**Attendu sur Serial Monitor (115200 baud):**
```
AeroPark Smart Parking System
Connexion WiFi...
Connecté! IP: 192.168.1.xxx
Force du signal: -65 dBm
Connexion au serveur...
Serveur connecté!
```

---

### Test B: Détection véhicule sur place A1
**Action:** Placer un objet devant le capteur IR de la place A1

**Attendu sur LCD:**
```
Place A1: OCCUPEE
Libres: 5/6
```

**Attendu sur Serial Monitor:**
```
Place a1: occupied
Envoi au serveur...
Réponse: {"success":true,"place_id":"a1","new_etat":"occupied"...}
```

**Attendu sur Backend (logs):**
```
INFO - Mise à jour capteur: a1 -> occupied
```

---

### Test C: Libération place A1
**Action:** Retirer l'objet du capteur IR de la place A1

**Attendu sur LCD:**
```
Place A1: LIBRE
Libres: 6/6
```

**Attendu sur Serial Monitor:**
```
Place a1: free
Envoi au serveur...
Réponse: {"success":true,"place_id":"a1","new_etat":"free"...}
```

---

### Test D: Barrière d'entrée
**Action:** Placer un objet devant le capteur IR d'entrée (GPIO 32)

**Attendu:**
1. Servo tourne à 90° (barrière ouvre)
2. LCD affiche: `Barrière: OUVERTE`
3. Après 5 secondes sans détection: Servo revient à 0° (barrière ferme)

---

### Test E: Barrière de sortie
**Action:** Placer un objet devant le capteur IR de sortie (GPIO 33)

**Attendu:**
1. Servo tourne à 90° (barrière ouvre)
2. LCD affiche: `Sortie: Ouvert`
3. Après 5 secondes: Servo revient à 0°

---

### Test F: Parking plein
**Action:** Occuper les 6 places (objets devant tous les capteurs IR)

**Attendu sur LCD:**
```
PARKING COMPLET!
Libres: 0/6
```

**Attendu:** Barrière d'entrée ne s'ouvre plus (optionnel selon config)

---

### Test G: Perte de connexion WiFi
**Action:** Désactiver temporairement le WiFi

**Attendu sur LCD:**
```
WiFi perdu!
Reconnexion...
```

**Attendu:** ESP32 tente de se reconnecter automatiquement

---

### Test H: Serveur inaccessible
**Action:** Arrêter le serveur backend

**Attendu sur Serial Monitor:**
```
Erreur HTTP: -1
Tentative reconnexion...
```

**Attendu:** ESP32 continue à fonctionner localement et réessaie

---

# PHASE 4 : Tests d'intégration complète

## 4.1 Scénario complet : Arrivée d'un véhicule

**Étapes:**
1. ESP32 et Backend en marche
2. Véhicule arrive à l'entrée (IR entrée détecte)
3. Barrière s'ouvre
4. Véhicule se gare sur place A1 (IR A1 détecte)
5. Backend reçoit la mise à jour
6. LCD met à jour le compteur

**Vérifications:**
- [ ] Barrière s'ouvre à la détection entrée
- [ ] LCD affiche la place occupée
- [ ] Backend enregistre le changement
- [ ] WebSocket envoie la notification
- [ ] Firestore contient le bon état

---

## 4.2 Scénario complet : Départ d'un véhicule

**Étapes:**
1. Place A1 occupée
2. Véhicule quitte la place A1 (IR A1 ne détecte plus)
3. Véhicule arrive à la sortie (IR sortie détecte)
4. Barrière s'ouvre
5. Véhicule sort

**Vérifications:**
- [ ] Place A1 passe à "free"
- [ ] Barrière sortie s'ouvre
- [ ] LCD met à jour le compteur
- [ ] Backend enregistre le changement

---

# PHASE 5 : Vérification Firebase

## 5.1 Vérifier les données dans Firestore

**URL:** https://console.firebase.google.com/project/aeropark-a191e/firestore

**Collection attendue:** `parking_places`

**Documents attendus:**
```
parking_places/
  ├── a1
  │   ├── place_id: "a1"
  │   ├── etat: "free" ou "occupied"
  │   ├── last_update: timestamp
  │   └── force_signal: -65
  ├── a2
  │   └── ...
  ├── a3
  │   └── ...
  ├── a4
  │   └── ...
  ├── a5
  │   └── ...
  └── a6
      └── ...
```

---

# 📊 Résumé des Tests

| Test | Endpoint/Action | Résultat Attendu |
|------|-----------------|------------------|
| Health Check | GET /health | status: "healthy" |
| Statut Parking | GET /api/v1/sensor/status | Liste 6 places |
| Update Capteur | POST /api/v1/sensor/update | success: true |
| Clé API invalide | Mauvais X-API-Key | 401 Unauthorized |
| WebSocket | ws://localhost:8000/ws/parking | connection_established |
| ESP32 Boot | Allumer ESP32 | LCD: "AeroPark Ready!" |
| Détection IR | Objet devant capteur | LCD met à jour |
| Barrière | IR entrée/sortie | Servo 0° ↔ 90° |

---

# 🔧 Commandes de Test Rapides (PowerShell)

```powershell
# Health Check
curl.exe http://localhost:8000/health

# Statut Parking
curl.exe -H "X-API-Key: aeropark-sensor-key-2024" http://localhost:8000/api/v1/sensor/status

# Simuler place occupée
curl.exe -X POST -H "Content-Type: application/json" -H "X-API-Key: aeropark-sensor-key-2024" -d "{\"place_id\":\"a1\",\"etat\":\"occupied\",\"force_signal\":-65}" http://localhost:8000/api/v1/sensor/update

# Simuler place libre
curl.exe -X POST -H "Content-Type: application/json" -H "X-API-Key: aeropark-sensor-key-2024" -d "{\"place_id\":\"a1\",\"etat\":\"free\",\"force_signal\":-65}" http://localhost:8000/api/v1/sensor/update
```

---

# ✅ Checklist Finale

## Backend
- [ ] Serveur démarre sans erreur
- [ ] Firebase connecté
- [ ] 6 places initialisées
- [ ] Health check répond
- [ ] Authentification API Key fonctionne
- [ ] Mise à jour capteur fonctionne
- [ ] WebSocket envoie les notifications

## ESP32
- [ ] Connexion WiFi réussie
- [ ] Connexion serveur réussie
- [ ] LCD affiche correctement
- [ ] 6 capteurs IR détectent
- [ ] Servo barrière fonctionne
- [ ] Mises à jour envoyées au serveur

## Firebase
- [ ] Collection parking_places existe
- [ ] 6 documents (a1-a6) présents
- [ ] États mis à jour en temps réel

---

**🎉 Si tous les tests passent, votre système AeroPark est prêt pour la production !**
