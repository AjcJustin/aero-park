# 🔐 AeroPark GOMA - Admin Authentication & Testing Guide

## Part 1: Understanding Admin Authentication

### 1.1 Why Admin Endpoints Reject Normal User Tokens

Admin endpoints in AeroPark use a **role-based access control (RBAC)** system:

```
Normal User → get_current_user() → role="user" → ❌ 403 Forbidden
Admin User  → get_current_user() → role="admin" → get_current_admin() → ✅ Access Granted
```

**The authentication flow:**
1. User sends Firebase ID token in `Authorization: Bearer <token>` header
2. Backend verifies token with Firebase Admin SDK
3. Backend checks user's `role` in Firestore (`users/{uid}` document)
4. If `role != "admin"`, returns **403 Forbidden**

**Code location:** `backend/security/firebase_auth.py`

```python
async def get_current_admin(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
```

---

### 1.2 How Admin Roles Work with Firebase

**Two-layer role storage:**

| Layer | Location | Purpose |
|-------|----------|---------|
| Firebase Custom Claims | `auth.set_custom_user_claims(uid, {"admin": True})` | Optional - for multi-project use |
| Firestore Document | `users/{uid}` with `role: "admin"` | **Primary - used by AeroPark** |

**AeroPark uses Firestore for roles** because:
- Easier to update without re-authentication
- Can be managed via admin dashboard
- Visible in Firebase Console

---

### 1.3 How to Create a DEV ADMIN Account Safely

#### Method 1: Firebase Console (Recommended for Dev)

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select project: **aeropark-a191e**
3. Navigate to **Firestore Database**
4. Create/Edit document: `users/{YOUR_USER_UID}`
5. Set fields:
   ```json
   {
     "uid": "YOUR_USER_UID",
     "email": "admin@aeropark.com",
     "role": "admin",
     "display_name": "Admin User",
     "created_at": "2026-01-22T00:00:00Z"
   }
   ```

#### Method 2: Python Script (One-time setup)

Create file `scripts/create_admin.py`:

```python
"""Create admin user in Firestore."""
import asyncio
import sys
sys.path.insert(0, '.')

from database.firebase_db import get_db, init_firebase

async def create_admin(user_uid: str, email: str):
    """Create admin user in Firestore."""
    init_firebase()
    db = get_db()
    
    await db.upsert_user_profile(user_uid, {
        "uid": user_uid,
        "email": email,
        "role": "admin",
        "display_name": "AeroPark Admin",
        "email_verified": True
    })
    
    print(f"✅ Admin user created: {email}")

if __name__ == "__main__":
    # Replace with your Firebase Auth user UID
    USER_UID = "YOUR_FIREBASE_AUTH_UID"
    EMAIL = "admin@aeropark.com"
    
    asyncio.run(create_admin(USER_UID, EMAIL))
```

Run: `python scripts/create_admin.py`

#### Method 3: API Endpoint (After first admin exists)

```bash
# Only existing admins can promote users
POST /admin/parking/promote-user
Authorization: Bearer <ADMIN_TOKEN>
Content-Type: application/json

{
  "user_uid": "target_user_uid",
  "role": "admin"
}
```

---

### 1.4 How to Obtain an Admin Token for Testing

#### Step 1: Create Admin Account in Firebase Auth

1. Go to Firebase Console → Authentication → Users
2. Click "Add user"
3. Email: `admin@aeropark.com`
4. Password: `SecureAdmin123!`
5. Copy the **User UID**

#### Step 2: Set Admin Role in Firestore

1. Go to Firestore → `users` collection
2. Create document with ID = User UID
3. Add field: `role: "admin"`

#### Step 3: Get ID Token via Firebase REST API

```bash
# Get ID token using Firebase Auth REST API
curl -X POST \
  'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=YOUR_FIREBASE_WEB_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "admin@aeropark.com",
    "password": "SecureAdmin123!",
    "returnSecureToken": true
  }'
```

**Response:**
```json
{
  "idToken": "eyJhbGciOiJSUzI1NiIs...", // ← USE THIS TOKEN
  "email": "admin@aeropark.com",
  "refreshToken": "...",
  "expiresIn": "3600"
}
```

#### Step 4: Use Token in Requests

```bash
curl -X GET http://localhost:8000/admin/parking/all \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

---

### 1.5 Testing Admin Endpoints

#### Using Postman

1. **Import Collection:**
   - Create new collection: "AeroPark Admin API"
   - Set variable: `{{BASE_URL}}` = `http://localhost:8000`
   - Set variable: `{{ADMIN_TOKEN}}` = your ID token

2. **Configure Authorization:**
   - Go to Collection → Authorization
   - Type: Bearer Token
   - Token: `{{ADMIN_TOKEN}}`

3. **Test Requests:**

| Request | Method | URL |
|---------|--------|-----|
| Get All Parking | GET | `{{BASE_URL}}/admin/parking/all` |
| Get Stats | GET | `{{BASE_URL}}/admin/parking/stats` |
| Get Reservations | GET | `{{BASE_URL}}/admin/parking/reservations` |
| Force Release | POST | `{{BASE_URL}}/admin/parking/force-release/a1` |
| Initialize Parking | POST | `{{BASE_URL}}/admin/parking/initialize` |

#### Using Frontend Admin Dashboard

1. Navigate to: `http://localhost:5500/admin/` (or your frontend URL)
2. Login with admin credentials
3. Frontend automatically:
   - Stores token in localStorage
   - Adds token to all API requests
   - Shows admin-only navigation

---

### 1.6 All Admin Actions & Step-by-Step Tests

#### Test 1: Initialize Parking (First Time Setup)
```bash
POST /admin/parking/initialize
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "success": true,
  "places_created": ["a1", "a2", "a3", "a4", "a5", "a6"]
}
```

#### Test 2: View All Parking Places
```bash
GET /admin/parking/all
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "places": [
    {"place_id": "a1", "etat": "free", ...},
    {"place_id": "a2", "etat": "occupied", ...}
  ]
}
```

#### Test 3: View Statistics
```bash
GET /admin/parking/stats
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "total": 6,
  "free": 4,
  "occupied": 1,
  "reserved": 1,
  "occupancy_rate": 33.33
}
```

#### Test 4: View All Reservations
```bash
GET /admin/parking/reservations
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "reservations": [...]
}
```

#### Test 5: Force Release Parking Spot
```bash
POST /admin/parking/force-release/a1
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "success": true,
  "place_id": "a1",
  "previous_state": "occupied",
  "new_state": "free"
}
```

#### Test 6: Cancel Reservation
```bash
POST /admin/parking/reservations/cancel/{reservation_id}
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "success": true,
  "reservation_id": "...",
  "refund_initiated": false
}
```

#### Test 7: Invalidate Access Code
```bash
POST /admin/parking/access-codes/invalidate/{code}
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "success": true,
  "code": "A7F",
  "invalidated_at": "2026-01-22T12:00:00Z"
}
```

#### Test 8: Refund Payment
```bash
POST /admin/parking/payments/refund/{payment_id}
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "success": true,
  "payment_id": "...",
  "refund_amount": 5000
}
```

#### Test 9: View Payment Logs
```bash
GET /admin/parking/payments
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "payments": [...]
}
```

#### Test 10: System Status
```bash
GET /admin/parking/system-status
Authorization: Bearer <ADMIN_TOKEN>

# Expected: 200 OK
{
  "status": "healthy",
  "database": "connected",
  "total_places": 6,
  "active_reservations": 2
}
```

---

## Quick Reference: Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 401 | Missing/Invalid token | Login again, get fresh token |
| 403 | Not admin | Set `role: "admin"` in Firestore |
| 404 | Endpoint not found | Check URL path |
| 422 | Validation error | Check request body |
| 500 | Server error | Check backend logs |

---

## Security Best Practices

1. **Never commit admin tokens** to version control
2. **Use environment variables** for sensitive data
3. **Rotate admin passwords** regularly
4. **Monitor admin actions** via audit logs
5. **Limit admin accounts** to essential personnel only
