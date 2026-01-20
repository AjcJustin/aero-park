# 🧪 Guide de Tests - AeroPark Smart System Backend

## � Tests Automatisés (pytest)

### Installation des dépendances de test
```bash
pip install pytest pytest-asyncio
```

### Exécution des tests

```bash
# Tous les tests (105 tests)
pytest tests/ -v

# Tests rapides (sans verbose)
pytest tests/ -q

# Un fichier spécifique
pytest tests/test_sensor.py -v

# Un test spécifique
pytest tests/test_access.py::TestAccessValidateCode::test_validate_code_requires_api_key -v
```

### Structure des tests
| Fichier | Description | Tests |
|---------|-------------|-------|
| `tests/conftest.py` | Fixtures partagées (API key, mock DB, mock users) | - |
| `tests/test_health.py` | Health check, documentation, CORS | 14 |
| `tests/test_sensor.py` | ESP32 sensor updates, health endpoint | 16 |
| `tests/test_parking.py` | Status, available, reserve, release | 18 |
| `tests/test_access.py` | Code validation, entry/exit, barrier | 16 |
| `tests/test_payment.py` | Mobile money, pricing, status | 16 |
| `tests/test_admin.py` | Admin endpoints, authentication | 22 |

### Résultat attendu
```
105 passed, 12 warnings in ~14s
```

---

## 📍 Accès à la Documentation API
- **URL:** http://localhost:8000/docs
- **API Key pour ESP32:** `aeropark-sensor-key-2024` (Header: `X-API-Key`)

---

## 🔬 TESTS MANUELS À EFFECTUER

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

### 5️⃣ TEST: Informations Parking pour Barrière
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

### 6️⃣ TEST: Mise à jour Capteur
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

### 7️⃣ TEST: Double TRUE Rule - Vérification Entrée
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

### 8️⃣ TEST: Validation Code d'Accès
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

### 9️⃣ TEST: Simulation Paiement Standard
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

### 🔟 TEST: Tarification
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

### Étape 3: Vérifier l'accès à l'entrée
```
POST /api/v1/barrier/check-entry-access
→ Vérifie si la barrière peut s'ouvrir
```

### Étape 4: Valider le code d'accès
```
POST /api/v1/access/validate-code
→ Avec le code obtenu à l'étape 2
```

### Étape 5: Mettre à jour le capteur (véhicule garé)
```
POST /api/v1/sensor/update
→ place_id: "a1", etat: "occupied"
```

### Étape 6: Vérifier le nouveau statut
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
   - `vehicle_presence == true` (capteur)
   - `access_code_valid == true` (code validé via app)

2. **Mobile Money:** 80% de succès simulé, 20% d'échec aléatoire

3. **Codes d'accès:** Expiration automatique (scheduler chaque minute)

---

## 🚀 DÉMARRAGE RAPIDE

```bash
# Démarrer le serveur
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Accéder à la documentation
# Ouvrir: http://localhost:8000/docs
```
