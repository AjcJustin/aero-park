# 🧪 Guide de Tests - AeroPark Smart System Backend

## 📍 Accès à la Documentation API
- **URL:** http://localhost:8000/docs
- **API Key pour ESP32:** `aeropark-sensor-key-2024` (Header: `X-API-Key`)

---

## 🔬 TESTS À EFFECTUER

### 1️⃣ TEST: Endpoint Racine (Health Check)
**Endpoint:** `GET /`

**Résultat Attendu:**
```json
{
  "message": "Bienvenue sur AeroPark Smart System API",
  "version": "1.0.0",
  "status": "running",
  "documentation": "/docs"
}
```

---

### 2️⃣ TEST: Statut du Parking
**Endpoint:** `GET /api/v1/parking/status`

**Résultat Attendu:**
```json
{
  "total_places": 6,
  "libres": 6,
  "occupees": 0,
  "reservees": 0,
  "places": [
    {"place_id": "a1", "etat": "free", ...},
    {"place_id": "a2", "etat": "free", ...},
    ...
  ]
}
```

---

### 3️⃣ TEST: Liste des Providers Mobile Money
**Endpoint:** `GET /api/v1/payment/mobile-money/providers`

**Résultat Attendu:**
```json
{
  "providers": [
    {"code": "ORANGE_MONEY", "name": "Orange Money", "description": "..."},
    {"code": "AIRTEL_MONEY", "name": "Airtel Money", "description": "..."},
    {"code": "MPESA", "name": "M-Pesa", "description": "..."}
  ]
}
```

---

### 4️⃣ TEST: Simulation Paiement Mobile Money (Succès ~80%)
**Endpoint:** `POST /api/v1/payment/mobile-money/simulate`

**Body:**
```json
{
  "provider": "ORANGE_MONEY",
  "phone_number": "0612345678",
  "amount": 500,
  "reservation_id": "test-reservation-001"
}
```

**Résultat Attendu (Succès):**
```json
{
  "success": true,
  "transaction_id": "TXN-XXXXXXXX",
  "provider": "ORANGE_MONEY",
  "amount": 500,
  "phone_number_masked": "******5678",
  "message": "Paiement Orange Money simulé avec succès",
  "reservation_status": "CONFIRMED",
  "access_code": "A7F"
}
```

**Résultat Attendu (Échec ~20%):**
```json
{
  "success": false,
  "transaction_id": null,
  "provider": "ORANGE_MONEY",
  "amount": 500,
  "phone_number_masked": "******5678",
  "message": "Échec du paiement: insufficient_balance",
  "reservation_status": "CANCELLED",
  "access_code": null
}
```

---

### 5️⃣ TEST: ESP32 Heartbeat
**Endpoint:** `POST /api/v1/esp32/heartbeat`

**Headers:**
```
X-API-Key: aeropark-sensor-key-2024
Content-Type: application/json
```

**Body:**
```json
{
  "device_id": "ESP32-BARRIER-001",
  "device_type": "BARRIER_CONTROLLER",
  "firmware_version": "2.0.0",
  "uptime_seconds": 3600,
  "free_heap": 45000,
  "wifi_rssi": -65,
  "sensor_status": {
    "ir_sensors": true,
    "servo": true,
    "lcd": true,
    "entry_sensor": true,
    "exit_sensor": true
  }
}
```

**Résultat Attendu:**
```json
{
  "acknowledged": true,
  "server_time": "2026-01-20T10:00:00.000000+00:00",
  "device_status": "ONLINE",
  "config_update_available": false,
  "pending_commands": [],
  "message": "Heartbeat acknowledged. Device status: ONLINE",
  "next_heartbeat_seconds": 30
}
```

---

### 6️⃣ TEST: Liste des Appareils ESP32
**Endpoint:** `GET /api/v1/esp32/devices`

**Headers:**
```
X-API-Key: aeropark-sensor-key-2024
```

**Résultat Attendu (après heartbeat):**
```json
[
  {
    "device_id": "ESP32-BARRIER-001",
    "device_type": "BARRIER_CONTROLLER",
    "status": "ONLINE",
    "last_seen": "2026-01-20T10:00:00.000000+00:00",
    "firmware_version": "2.0.0",
    "uptime_seconds": 3600,
    "wifi_rssi": -65,
    "ip_address": "127.0.0.1",
    "total_heartbeats": 1
  }
]
```

---

### 7️⃣ TEST: Santé de la Flotte ESP32
**Endpoint:** `GET /api/v1/esp32/health`

**Headers:**
```
X-API-Key: aeropark-sensor-key-2024
```

**Résultat Attendu:**
```json
{
  "total_devices": 1,
  "online": 1,
  "offline": 0,
  "degraded": 0,
  "health_percentage": 100.0,
  "checked_at": "2026-01-20T10:00:00.000000+00:00"
}
```

---

### 8️⃣ TEST: Informations Parking pour Barrière
**Endpoint:** `GET /api/v1/barrier/parking-info`

**Headers:**
```
X-API-Key: aeropark-sensor-key-2024
```

**Résultat Attendu:**
```json
{
  "total_spots": 6,
  "free_spots": 6,
  "occupied_spots": 0,
  "reserved_spots": 0,
  "allow_entry": true,
  "require_code": false,
  "message": "Bienvenue! Places disponibles."
}
```

---

### 9️⃣ TEST: Mise à jour Capteur ESP32
**Endpoint:** `POST /api/v1/sensor/update`

**Headers:**
```
X-API-Key: aeropark-sensor-key-2024
Content-Type: application/json
```

**Body:**
```json
{
  "place_id": "a1",
  "etat": "occupied",
  "force_signal": -55
}
```

**Résultat Attendu:**
```json
{
  "success": true,
  "place_id": "a1",
  "new_etat": "occupied",
  "message": "État de la place mis à jour",
  "timestamp": "2026-01-20T10:00:00.000000"
}
```

---

### 🔟 TEST: Double TRUE Rule - Vérification Entrée
**Endpoint:** `POST /api/v1/barrier/check-entry-access`

**Headers:**
```
X-API-Key: aeropark-sensor-key-2024
Content-Type: application/json
```

**Body (véhicule détecté, places disponibles):**
```json
{
  "barrier_id": "entry",
  "sensor_presence": true
}
```

**Résultat Attendu (places libres):**
```json
{
  "access_granted": true,
  "reason": "spots_available",
  "message": "Bienvenue! Entrez et choisissez une place.",
  "free_spots": 5,
  "open_barrier": true
}
```

---

### 1️⃣1️⃣ TEST: Validation Code d'Accès
**Endpoint:** `POST /api/v1/access/validate-code`

**Headers:**
```
X-API-Key: aeropark-sensor-key-2024
Content-Type: application/json
```

**Body:**
```json
{
  "code": "A7F",
  "sensor_presence": true,
  "barrier_id": "entry"
}
```

**Résultat Attendu (code valide):**
```json
{
  "valid": true,
  "access_granted": true,
  "message": "Code valide - Accès autorisé",
  "place_id": "a1",
  "user_email": "user@example.com"
}
```

**Résultat Attendu (code invalide):**
```json
{
  "valid": false,
  "access_granted": false,
  "message": "Code invalide ou expiré",
  "place_id": null,
  "user_email": null
}
```

---

### 1️⃣2️⃣ TEST: Simulation Paiement Standard
**Endpoint:** `POST /api/v1/payment/simulate`

**Body:**
```json
{
  "reservation_id": "test-123",
  "amount": 500,
  "payment_method": "MOBILE_MONEY"
}
```

**Résultat Attendu:**
```json
{
  "success": true,
  "transaction_id": "SIM-XXXXXXXX",
  "amount": 500,
  "message": "Paiement simulé avec succès"
}
```

---

### 1️⃣3️⃣ TEST: Tarification
**Endpoint:** `GET /api/v1/payment/pricing`

**Résultat Attendu:**
```json
{
  "hourly_rate": 100,
  "currency": "XAF",
  "minimum_duration_minutes": 15,
  "maximum_duration_minutes": 480
}
```

---

## 🔄 SCÉNARIO DE TEST COMPLET (Flux Utilisateur)

### Étape 1: Vérifier le statut du parking
```
GET /api/v1/parking/status
→ Vérifie qu'il y a des places libres
```

### Étape 2: Simuler un paiement Mobile Money
```
POST /api/v1/payment/mobile-money/simulate
→ Obtenir un code d'accès (ex: "A7F")
```

### Étape 3: Envoyer un heartbeat ESP32
```
POST /api/v1/esp32/heartbeat
→ Confirme que l'ESP32 est en ligne
```

### Étape 4: Vérifier l'accès à l'entrée
```
POST /api/v1/barrier/check-entry-access
→ Vérifie si la barrière peut s'ouvrir
```

### Étape 5: Valider le code d'accès
```
POST /api/v1/access/validate-code
→ Avec le code obtenu à l'étape 2
```

### Étape 6: Mettre à jour le capteur (véhicule garé)
```
POST /api/v1/sensor/update
→ place_id: "a1", etat: "occupied"
```

### Étape 7: Vérifier le nouveau statut
```
GET /api/v1/parking/status
→ Vérifie que la place est occupée
```

---

## ⚠️ ERREURS COURANTES

| Code | Message | Cause |
|------|---------|-------|
| 401 | "Invalid API key" | Header X-API-Key manquant ou incorrect |
| 404 | "Place not found" | ID de place invalide (doit être a1-a6) |
| 422 | Validation Error | Body JSON mal formaté |

---

## 🔐 NOTES IMPORTANTES

1. **Double TRUE Rule:** La barrière s'ouvre UNIQUEMENT si:
   - `vehicle_presence == true` (capteur ESP32)
   - `access_code_valid == true` (code validé via app)

2. **Mobile Money:** 80% de succès simulé, 20% d'échec aléatoire

3. **Codes d'accès:** Expiration automatique (scheduler chaque minute)

4. **Heartbeat ESP32:** Recommandé toutes les 30 secondes

---

## 🚀 DÉMARRAGE RAPIDE

```bash
# Démarrer le serveur
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Accéder à la documentation
# Ouvrir: http://localhost:8000/docs
```
