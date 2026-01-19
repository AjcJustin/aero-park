# AeroPark Smart System

Système de gestion de parking aéroportuaire intelligent avec intégration IoT ESP32, mises à jour en temps réel via WebSocket, et authentification Firebase.

## 🚀 Fonctionnalités

- **Monitoring en Temps Réel**: 6 capteurs IR ESP32 détectent la présence des véhicules
- **Réservations Intelligentes**: Les utilisateurs réservent des places avec expiration automatique
- **Mises à Jour Live**: WebSocket diffuse les changements d'état instantanément
- **Barrière Automatique**: Servo-moteur contrôlé par l'ESP32
- **Affichage LCD**: Écran I2C affichant l'état du parking
- **Authentification Sécurisée**: Firebase Auth pour les utilisateurs, clé API pour les capteurs

## 📁 Structure du Projet

```
aeropack/
├── backend/                    # Backend FastAPI
│   ├── main.py                 # Point d'entrée
│   ├── config.py               # Configuration
│   ├── requirements.txt        # Dépendances Python
│   ├── .env                    # Variables d'environnement
│   ├── routers/                # Routes API
│   │   ├── auth.py             # Authentification utilisateurs
│   │   ├── parking.py          # Opérations parking
│   │   ├── admin.py            # Administration
│   │   ├── sensor.py           # Routes capteurs ESP32
│   │   └── websocket.py        # Gestionnaire WebSocket
│   ├── services/               # Logique métier
│   │   ├── parking_service.py
│   │   ├── reservation_service.py
│   │   └── websocket_service.py
│   ├── models/                 # Modèles Pydantic
│   │   ├── parking.py          # place_id, etat, force_signal
│   │   └── user.py
│   ├── security/               # Sécurité
│   │   ├── firebase_auth.py
│   │   └── api_key.py          # Validation clé API
│   ├── database/               # Couche base de données
│   │   └── firebase_db.py      # Opérations Firestore
│   └── utils/
│       ├── scheduler.py
│       └── helpers.py
├── esp32/                      # Client ESP32
│   └── aeropark_sensor/
│       └── aeropark_sensor.ino # Code Arduino
└── README.md
```

## 🔌 Matériel ESP32

### Composants
- **ESP32 DevKit** - Microcontrôleur principal
- **6 Capteurs IR** - Détection places (a1-a6)
- **2 Capteurs IR** - Entrée/Sortie
- **1 Servo SG90** - Barrière
- **1 LCD I2C 16x2** - Affichage

### Branchements
| Composant | GPIO ESP32 |
|-----------|------------|
| IR Place a1 | GPIO 13 |
| IR Place a2 | GPIO 14 |
| IR Place a3 | GPIO 25 |
| IR Place a4 | GPIO 26 |
| IR Place a5 | GPIO 27 |
| IR Place a6 | GPIO 34 |
| IR Entrée | GPIO 32 |
| IR Sortie | GPIO 33 |
| Servo | GPIO 4 |
| LCD SDA | GPIO 21 |
| LCD SCL | GPIO 22 |

## 🚀 Installation Rapide

### 1. Backend Setup

```bash
cd aeropack/backend

# Créer environnement virtuel
python -m venv venv

# Activer (Windows)
venv\Scripts\activate

# Installer dépendances
pip install -r requirements.txt
```

### 2. Configuration Firebase

Votre `.env` est déjà configuré. Vérifiez que les valeurs sont correctes:

```env
FIREBASE_PROJECT_ID="aeropark-a191e"
FIREBASE_PRIVATE_KEY="..." 
FIREBASE_CLIENT_EMAIL="..."

# Clé API ESP32 (IDENTIQUE dans le code Arduino)
SENSOR_API_KEY=aeropark-sensor-key-2024

# Paramètres
TOTAL_PARKING_SLOTS=6
```

### 3. Lancer le Backend

```bash
# Depuis le dossier backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Le serveur démarre sur `http://localhost:8000`

### 4. Vérification

- Documentation Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## 📡 Endpoints ESP32

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/v1/sensor/update` | POST | Mise à jour état place |
| `/api/v1/sensor/health` | GET | Vérification connexion |
| `/ws/parking` | WebSocket | Notifications réservations |

### Format de Requête (ESP32 → Backend)

```json
{
    "place_id": "a1",
    "etat": "occupied",
    "force_signal": -55
}
```

### Headers Requis
```
Content-Type: application/json
X-API-Key: aeropark-sensor-key-2024
```

### Format WebSocket (Backend → ESP32)

Notification de réservation:
```json
{
    "type": "reservation",
    "donnees": {
        "place_id": 1,
        "action": "create"
    }
}
```

## 🔧 Configuration ESP32

Dans `esp32/aeropark_sensor/aeropark_sensor.ino`, modifiez:

```cpp
// WiFi
const char* ssid = "VOTRE_SSID";
const char* password = "VOTRE_MOT_DE_PASSE";

// Serveur (IP de votre PC sur le même réseau)
const char* serverHost = "192.168.1.100";
const int serverPort = 8000;

// Clé API (doit correspondre au backend)
const char* apiKey = "aeropark-sensor-key-2024";
```

### Bibliothèques Arduino Requises

Dans Arduino IDE, installer via Library Manager:
- `ArduinoJson` (by Benoit Blanchon)
- `WebSockets` (by Markus Sattler)
- `ESP32Servo`
- `LiquidCrystal I2C`

## 📱 API Utilisateurs (Mobile/Web)

### Voir l'état du parking
```
GET /parking/status
```

### Réserver une place (authentifié)
```
POST /parking/reserve
Authorization: Bearer <firebase_id_token>

{
    "place_id": "a1",
    "duration_minutes": 60
}
```

### Libérer une place
```
POST /parking/release/a1
Authorization: Bearer <firebase_id_token>
```

## 🔐 Sécurité

- **Capteurs ESP32**: Clé API dans header `X-API-Key`
- **Utilisateurs**: Token Firebase dans header `Authorization: Bearer <token>`
- **CORS**: Configuré pour accepter toutes les origines (`*`)

## 🧪 Test Rapide

1. Démarrer le backend:
   ```bash
   cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. Tester l'endpoint sensor avec curl:
   ```bash
   curl -X POST http://localhost:8000/api/v1/sensor/update \
     -H "Content-Type: application/json" \
     -H "X-API-Key: aeropark-sensor-key-2024" \
     -d '{"place_id": "a1", "etat": "occupied", "force_signal": -50}'
   ```

3. Vérifier la réponse:
   ```json
   {
     "success": true,
     "place_id": "a1",
     "new_etat": "occupied",
     "message": "Place a1 mise à jour",
     "timestamp": "2024-..."
   }
   ```

## 📊 Collection Firestore

Le backend crée automatiquement la collection `parking_places` avec les documents:

```
parking_places/
├── a1: { place_id: "a1", etat: "free", ... }
├── a2: { place_id: "a2", etat: "free", ... }
├── a3: { place_id: "a3", etat: "free", ... }
├── a4: { place_id: "a4", etat: "free", ... }
├── a5: { place_id: "a5", etat: "free", ... }
└── a6: { place_id: "a6", etat: "free", ... }
```

## 🐳 Docker (Optionnel)

```bash
cd backend
docker build -t aeropark-backend .
docker run -p 8000:8000 --env-file .env aeropark-backend
```

## ⚠️ Dépannage

### ESP32 ne se connecte pas au WiFi
- Vérifier SSID et mot de passe
- ESP32 supporte uniquement WiFi 2.4GHz

### Erreur 401 Unauthorized
- Vérifier que `X-API-Key` est exactement `aeropark-sensor-key-2024`
- Vérifier que `SENSOR_API_KEY` dans `.env` correspond

### WebSocket ne se connecte pas
- Vérifier que le port 8000 est ouvert
- Utiliser l'IP locale du serveur (pas localhost)

### Firebase Connection Error
- Vérifier les credentials Firebase dans `.env`
- S'assurer que Firestore est activé dans la console Firebase

---

**AeroPark Smart System** - Projet de fin d'études
   ```bash
   cp .env.example .env
   # Edit .env with your Firebase credentials and API keys
   ```

6. **Run the server:**
   ```bash
   # Development
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   
   # Production
   uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

7. **Access the API:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - WebSocket: ws://localhost:8000/ws/parking

### ESP32 Setup

1. **Install Arduino IDE** (or PlatformIO)

2. **Install ESP32 board support:**
   - File → Preferences → Additional Board Manager URLs
   - Add: `https://dl.espressif.com/dl/package_esp32_index.json`
   - Tools → Board → Boards Manager → Search "esp32" → Install

3. **Install required libraries:**
   - ArduinoJson (by Benoit Blanchon)

4. **Configure the sketch:**
   Open `esp32/parking_sensor/parking_sensor.ino` and update:
   ```cpp
   const char* WIFI_SSID = "YOUR_WIFI_SSID";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   const char* SERVER_HOST = "YOUR_SERVER_IP";
   const char* API_KEY = "YOUR_SENSOR_API_KEY";
   const char* SPOT_ID = "YOUR_SPOT_ID";
   ```

5. **Hardware wiring (HC-SR04):**
   | HC-SR04 Pin | ESP32 Pin |
   |-------------|-----------|
   | VCC         | 5V        |
   | GND         | GND       |
   | TRIG        | GPIO 5    |
   | ECHO        | GPIO 18   |

6. **Upload and monitor:**
   - Select board: Tools → Board → ESP32 Dev Module
   - Select port: Tools → Port → (your COM port)
   - Upload sketch
   - Open Serial Monitor (115200 baud)

## 📡 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/me` | Get current user profile |
| GET | `/users/me/reservation` | Get user's active reservation |

### Parking
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/parking/status` | Get all spots status |
| GET | `/parking/available` | Get available spots only |
| GET | `/parking/spot/{id}` | Get specific spot details |
| POST | `/parking/reserve` | Reserve a parking spot |
| POST | `/parking/release` | Release reserved spot |
| POST | `/parking/extend` | Extend reservation time |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/parking/all` | Get all spots (admin) |
| GET | `/admin/parking/stats` | Get parking statistics |
| POST | `/admin/parking/add` | Add new parking spot |
| PUT | `/admin/parking/{id}` | Update spot configuration |
| DELETE | `/admin/parking/{id}` | Delete parking spot |
| POST | `/admin/parking/force-release/{id}` | Force release any spot |
| POST | `/admin/parking/initialize` | Initialize default spots |

### Sensor
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sensor/update` | Report spot occupancy |
| POST | `/sensor/heartbeat` | Sensor keep-alive |
| GET | `/sensor/config/{id}` | Get sensor configuration |
| POST | `/sensor/batch-update` | Batch sensor updates |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `/ws/parking` | Real-time parking updates |
| GET `/ws/status` | WebSocket connection stats |

## 🔐 Authentication

### User Authentication
Users authenticate via Firebase ID tokens:
```http
Authorization: Bearer <firebase-id-token>
```

### Sensor Authentication
ESP32 sensors authenticate via API key:
```http
X-API-Key: <sensor-api-key>
X-Sensor-ID: <sensor-identifier>
```

### Admin Authentication
Admins need both Firebase auth (with admin role) and may use admin API key for additional security.

## 🔄 Parking State Flow

```
AVAILABLE ──(user reserves)──> RESERVED
    ↑                              │
    │                              │
(vehicle leaves                (vehicle arrives
 or expiry)                    - sensor detects)
    │                              │
    ↑                              ↓
AVAILABLE <──(vehicle leaves)── OCCUPIED
```

## 🔌 WebSocket Events

Connect to `ws://localhost:8000/ws/parking` to receive real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/parking');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'connected':
            console.log('Connected to parking updates');
            break;
        case 'initial_status':
            console.log('Current parking status:', data.data);
            break;
        case 'spot_update':
            console.log('Spot changed:', data.event, data.data);
            break;
        case 'reservation_created':
            console.log('New reservation:', data.data);
            break;
        case 'sensor_update':
            console.log('Sensor update:', data.data);
            break;
    }
};

// Request current status
ws.send(JSON.stringify({ type: 'get_status' }));

// Keep-alive ping
ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
```

## 📊 Example API Calls

### Reserve a Parking Spot
```bash
curl -X POST "http://localhost:8000/parking/reserve" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "spot_id": "SPOT_ID_HERE",
    "duration_minutes": 60
  }'
```

### Sensor Status Update
```bash
curl -X POST "http://localhost:8000/sensor/update" \
  -H "X-API-Key: YOUR_SENSOR_API_KEY" \
  -H "X-Sensor-ID: ESP32-SENSOR-001" \
  -H "Content-Type: application/json" \
  -d '{
    "spot_id": "SPOT_ID_HERE",
    "status": "occupied",
    "distance_cm": 25.5
  }'
```

### Add New Parking Spot (Admin)
```bash
curl -X POST "http://localhost:8000/admin/parking/add" \
  -H "Authorization: Bearer ADMIN_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "spot_number": "B1",
    "zone": "Terminal 2",
    "floor": 1,
    "sensor_id": "ESP32-SENSOR-006"
  }'
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `FIREBASE_PROJECT_ID` | Firebase project ID | Yes |
| `FIREBASE_PRIVATE_KEY` | Service account private key | Yes |
| `FIREBASE_CLIENT_EMAIL` | Service account email | Yes |
| `FIREBASE_DATABASE_URL` | Firestore database URL | Yes |
| `SENSOR_API_KEY` | API key for ESP32 sensors | Yes |
| `ADMIN_API_KEY` | API key for admin operations | Yes |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | No |
| `DEBUG` | Enable debug mode | No |
| `DEFAULT_RESERVATION_DURATION_MINUTES` | Default reservation time | No |
| `MAX_RESERVATION_DURATION_MINUTES` | Maximum reservation time | No |

## 🧪 Testing

### Initialize Test Data
After starting the server, initialize default parking spots:
```bash
curl -X POST "http://localhost:8000/admin/parking/initialize" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### Test Sensor Updates
Use the mock ESP32 behavior:
```bash
# Report spot as occupied
curl -X POST "http://localhost:8000/sensor/update" \
  -H "X-API-Key: your-sensor-api-key" \
  -d '{"spot_id": "SPOT_ID", "status": "occupied"}'

# Report spot as free
curl -X POST "http://localhost:8000/sensor/update" \
  -H "X-API-Key: your-sensor-api-key" \
  -d '{"spot_id": "SPOT_ID", "status": "free"}'
```

## 🚀 Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/ .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Cloud Run / Cloud Functions
The application is ready for deployment to Google Cloud Run or similar platforms. Ensure environment variables are configured in your cloud provider.

## 📝 Future Enhancements

- [ ] Payment integration (Stripe/PayPal)
- [ ] Mobile app (React Native)
- [ ] License plate recognition (OpenCV/ML)
- [ ] Multi-floor parking visualization
- [ ] Parking guidance system
- [ ] Analytics dashboard
- [ ] Rate limiting and quotas
- [ ] Email/SMS notifications

## 📄 License

This project is proprietary software for AeroPark Smart System.

## 👥 Support

For support and inquiries, contact the AeroPark development team.
