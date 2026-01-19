# AeroPark Smart System

A comprehensive, production-ready airport parking management system featuring IoT integration with ESP32 sensors, real-time updates via WebSocket, and Firebase authentication.

## 🚀 Features

- **Real-time Parking Monitoring**: ESP32 sensors detect vehicle presence using ultrasonic sensors
- **Smart Reservations**: Users can reserve spots for specified durations with automatic expiry
- **Live Updates**: WebSocket endpoint broadcasts parking status changes instantly
- **Secure Authentication**: Firebase Authentication for users, API keys for sensors
- **Concurrent Handling**: Firestore transactions prevent race conditions
- **Background Tasks**: Automatic reservation expiry handling
- **Admin Dashboard API**: Manage spots, view statistics, force releases

## 📁 Project Structure

```
aeropack/
├── backend/                    # FastAPI Backend
│   ├── main.py                 # Application entry point
│   ├── config.py               # Configuration management
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example            # Environment template
│   ├── routers/                # API route handlers
│   │   ├── auth.py             # User authentication routes
│   │   ├── parking.py          # Parking operations routes
│   │   ├── admin.py            # Admin management routes
│   │   ├── sensor.py           # ESP32 sensor routes
│   │   └── websocket.py        # WebSocket handler
│   ├── services/               # Business logic layer
│   │   ├── parking_service.py  # Parking operations
│   │   ├── reservation_service.py # Reservation handling
│   │   └── websocket_service.py # WebSocket management
│   ├── models/                 # Pydantic data models
│   │   ├── parking.py          # Parking spot models
│   │   └── user.py             # User profile models
│   ├── security/               # Authentication & authorization
│   │   ├── firebase_auth.py    # Firebase token verification
│   │   └── api_key.py          # API key validation
│   ├── database/               # Database layer
│   │   └── firebase_db.py      # Firestore operations
│   └── utils/                  # Utility modules
│       ├── scheduler.py        # Background task scheduler
│       └── helpers.py          # Helper functions
├── esp32/                      # ESP32 Sensor Client
│   └── parking_sensor/
│       └── parking_sensor.ino  # Arduino sketch
└── README.md                   # This file
```

## 🛠️ Tech Stack

### Backend
- **Python 3.10+**
- **FastAPI** - Modern async web framework
- **Firebase Admin SDK** - Authentication & Firestore
- **Pydantic** - Data validation
- **APScheduler** - Background task scheduling
- **Uvicorn** - ASGI server

### IoT Client
- **ESP-32D** microcontroller
- **HC-SR04** ultrasonic sensor
- **Arduino IDE** compatible

## 🚀 Quick Start

### Backend Setup

1. **Clone and navigate to backend:**
   ```bash
   cd aeropack/backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Firebase:**
   - Go to [Firebase Console](https://console.firebase.google.com/)
   - Create a new project (or use existing)
   - Enable Authentication (Email/Password provider)
   - Create Firestore Database
   - Generate service account key:
     - Project Settings → Service Accounts → Generate New Private Key
   - Copy `.env.example` to `.env` and fill in your credentials

5. **Configure environment:**
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
