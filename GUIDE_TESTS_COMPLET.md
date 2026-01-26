# AeroPark GOMA - Guide de Test Complet
## Plan de Validation Avant Production

---

# TABLE DES MATIÈRES

1. [Configuration Préalable](#1-configuration-préalable)
2. [Tests Manuels - Utilisateurs](#2-tests-manuels---utilisateurs)
3. [Tests Manuels - Admin](#3-tests-manuels---admin)
4. [Scripts de Test API](#4-scripts-de-test-api)
5. [Checklist de Débogage](#5-checklist-de-débogage)
6. [Vérification Frontend](#6-vérification-frontend)
7. [Tests ESP32/Capteurs](#7-tests-esp32capteurs)

---

# 1. CONFIGURATION PRÉALABLE

## 1.1 Démarrer le Backend

```powershell
cd c:\Users\abrah\OneDrive\Desktop\aeropack\backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Vérification:** Ouvrir http://localhost:8000/docs → Swagger UI doit s'afficher

## 1.2 Démarrer le Frontend

```powershell
cd c:\Users\abrah\OneDrive\Desktop\aeropack\frontend
# Utiliser un serveur HTTP simple
python -m http.server 3000
```

**Vérification:** Ouvrir http://localhost:3000 → Page d'accueil AeroPark

## 1.3 Créer un Utilisateur Admin dans Firebase

### Étape 1: Créer un compte Firebase
1. Aller sur https://console.firebase.google.com
2. Sélectionner le projet `aeropark-a191e`
3. Aller dans **Authentication** → **Users**
4. Cliquer **Add user**
5. Entrer: `admin@aeropark.com` / mot de passe fort

### Étape 2: Ajouter le rôle admin dans Firestore
1. Aller dans **Firestore Database**
2. Créer/modifier la collection `users`
3. Créer un document avec l'UID de l'utilisateur admin
4. Ajouter le champ: `role: "admin"`

```json
{
  "uid": "FIREBASE_USER_UID",
  "email": "admin@aeropark.com",
  "role": "admin",
  "displayName": "Administrateur"
}
```

### Étape 3: Vérifier dans le backend
Le backend vérifie le rôle dans `security/firebase_auth.py` via `get_current_admin()`

---

# 2. TESTS MANUELS - UTILISATEURS

## Test U-01: Inscription Utilisateur

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Ouvrir `/frontend/pages/public/register.html` | Page inscription s'affiche |
| 2 | Remplir: Nom, Email, Mot de passe (8+ chars) | Champs validés |
| 3 | Cocher "J'accepte les conditions" | Case cochée |
| 4 | Cliquer "Créer mon Compte" | Spinner de chargement |
| 5 | Attendre | Toast "Compte Créé" + Redirection dashboard |

**Vérification Firebase:** Nouveau user dans Authentication

---

## Test U-02: Connexion Utilisateur

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Ouvrir `/frontend/pages/public/login.html` | Page connexion s'affiche |
| 2 | Entrer email + mot de passe valides | Champs remplis |
| 3 | Cliquer "Se Connecter" | Spinner de chargement |
| 4 | Attendre | Toast "Connexion Réussie" |
| 5 | Vérifier redirection | Dashboard utilisateur |
| 6 | Vérifier localStorage | `aeropark_token` présent |

**Test négatif:** Email invalide → Message d'erreur
**Test négatif:** Mot de passe incorrect → Message d'erreur

---

## Test U-03: Connexion Google

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Cliquer "Continuer avec Google" | Popup Google s'ouvre |
| 2 | Sélectionner compte Google | Authentification |
| 3 | Attendre | Redirection dashboard |

---

## Test U-04: Voir État du Parking (Page Accueil)

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Ouvrir `/frontend/index.html` | Page accueil |
| 2 | Scroller vers "État du Parking" | Grille parking visible |
| 3 | Vérifier statistiques | Compteurs: Disponibles, Réservées, Occupées |
| 4 | Vérifier couleurs | 🟢 Libre, 🟡 Réservée, 🔴 Occupée |
| 5 | Cliquer "Actualiser" | Données rechargées |

---

## Test U-05: Réserver une Place

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Être connecté | Token valide |
| 2 | Cliquer sur place verte (libre) | Modal de réservation s'ouvre |
| 3 | Sélectionner date/heure début | Champ rempli |
| 4 | Sélectionner date/heure fin | Champ rempli |
| 5 | Entrer plaque véhicule | Ex: "CD-123-GO" |
| 6 | Vérifier coût estimé | Calcul automatique ($5/heure) |
| 7 | Cliquer "Confirmer" | Spinner de traitement |
| 8 | Attendre | Toast "Réservation Confirmée" |
| 9 | Vérifier place | Couleur → 🟡 Réservée |
| 10 | Vérifier redirection | Page réservations |

**État place:** `free` → `reserved`

---

## Test U-06: Consulter Mes Réservations

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Aller `/frontend/pages/user/reservations.html` | Page réservations |
| 2 | Vérifier liste | Réservation créée visible |
| 3 | Vérifier statut | Badge "Réservé" ou "Actif" |
| 4 | Vérifier détails | Place, dates, durée, véhicule |
| 5 | Vérifier boutons | "Code d'Accès", "Prolonger", "Annuler" |

---

## Test U-07: Générer Code d'Accès

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Aller `/frontend/pages/user/access-codes.html` | Page codes d'accès |
| 2 | Sélectionner réservation | Dropdown peuplé |
| 3 | Sélectionner type "Entrée" | Bouton sélectionné |
| 4 | Cliquer "Générer le Code" | Spinner |
| 5 | Attendre | Code 6 chiffres affiché |
| 6 | Vérifier compte à rebours | Ex: "Valide pour: 14m 30s" |
| 7 | Cliquer "Copier" | Toast "Code copié" |

**Le code doit:** 
- Être à 3 caractères (format ESP32) ou 6 chiffres
- Avoir une expiration de 15 minutes
- Apparaître dans "Codes Récents"

---

## Test U-08: Simuler Paiement Orange Money

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Aller `/frontend/pages/user/payments.html` | Page paiements |
| 2 | Vérifier "Paiements en Attente" | Réservation listée |
| 3 | Cliquer "Payer" | Formulaire apparaît |
| 4 | Sélectionner "Orange Money" | Méthode sélectionnée (bordure orange) |
| 5 | Entrer numéro: `+243999000000` | Champ rempli |
| 6 | Cliquer "Payer Maintenant" | Spinner |
| 7 | Attendre (2-3 sec simulation) | Toast "Paiement effectué" |
| 8 | Vérifier historique | Nouveau paiement statut "Complété" |

**Tester aussi:** Airtel Money, M-Pesa

---

## Test U-09: Annuler Réservation

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Page réservations | Réservation visible |
| 2 | Cliquer "Annuler" | Confirmation demandée |
| 3 | Confirmer | Réservation disparaît |
| 4 | Vérifier parking | Place redevient 🟢 libre |

**État place:** `reserved` → `free`

---

## Test U-10: Prolonger Réservation

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Réservation active | Bouton "Prolonger" visible |
| 2 | Cliquer "Prolonger" | Modal s'ouvre |
| 3 | Sélectionner nouvelle fin | +2 heures |
| 4 | Vérifier coût additionnel | Calcul affiché |
| 5 | Confirmer | Toast "Réservation prolongée" |

---

## Test U-11: Déconnexion

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Cliquer "Déconnexion" | Action exécutée |
| 2 | Attendre | Toast "Déconnexion réussie" |
| 3 | Vérifier redirection | Page login |
| 4 | Vérifier localStorage | Token supprimé |

---

## Test U-12: Mode Hors Ligne

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Se connecter normalement | Token stocké |
| 2 | Désactiver réseau (DevTools > Network > Offline) | Hors ligne |
| 3 | Rafraîchir page | Bannière "Hors ligne" visible |
| 4 | Vérifier codes | Dernier code en cache affiché |

---

# 3. TESTS MANUELS - ADMIN

## Test A-01: Connexion Admin

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Login avec `admin@aeropark.com` | Connexion réussie |
| 2 | Vérifier localStorage | `aeropark_role` = "admin" |
| 3 | Vérifier redirection | Dashboard admin |
| 4 | Vérifier menu | Liens admin visibles |

---

## Test A-02: Dashboard Admin

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Ouvrir `/frontend/pages/admin/dashboard.html` | Dashboard admin |
| 2 | Vérifier statistiques | Places totales, libres, occupées, taux |
| 3 | Vérifier graphiques | Données affichées |
| 4 | Vérifier activité récente | Liste des événements |

---

## Test A-03: Gestion des Places

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Ouvrir `/frontend/pages/admin/places.html` | Liste des places |
| 2 | Vérifier grille | Toutes les places visibles |
| 3 | Cliquer sur place occupée | Détails affichés |
| 4 | Cliquer "Libérer" | Confirmation demandée |
| 5 | Confirmer | Place devient libre |

---

## Test A-04: Forcer Libération

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Sélectionner place réservée/occupée | Actions disponibles |
| 2 | Cliquer "Forcer Libération" | Modal confirmation |
| 3 | Entrer raison (optionnel) | Champ texte |
| 4 | Confirmer | Place → `free` |
| 5 | Vérifier logs | Action enregistrée |

---

## Test A-05: Voir Tous les Codes d'Accès

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Page admin codes | Liste tous les codes |
| 2 | Filtrer par statut | "Actif", "Utilisé", "Expiré" |
| 3 | Voir détails code | User, place, expiration |

---

## Test A-06: Invalider Code d'Accès

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Trouver code actif | Dans la liste |
| 2 | Cliquer "Invalider" | Confirmation |
| 3 | Confirmer | Code → statut "invalidé" |
| 4 | Tester code à la barrière | Accès refusé |

---

## Test A-07: Voir Tous les Paiements

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Ouvrir `/frontend/pages/admin/payments.html` | Liste paiements |
| 2 | Vérifier colonnes | Date, User, Montant, Méthode, Statut |
| 3 | Filtrer par statut | "Complété", "En attente", "Échoué" |
| 4 | Voir totaux | Somme des paiements |

---

## Test A-08: Voir Tous les Utilisateurs

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Ouvrir `/frontend/pages/admin/users.html` | Liste utilisateurs |
| 2 | Vérifier infos | Email, Nom, Rôle, Date inscription |
| 3 | Voir statistiques user | Nb réservations, heures parking |

---

## Test A-09: Statut Système

| Étape | Action | Résultat Attendu |
|-------|--------|------------------|
| 1 | Page settings/système | Infos système |
| 2 | Vérifier statuts | Firebase: ✅, Scheduler: ✅ |
| 3 | Voir connexions WebSocket | Nombre de clients |

---

# 4. SCRIPTS DE TEST API

## 4.1 Variables d'Environnement

```powershell
# Définir le token (récupérer depuis localStorage après login)
$TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
$API_KEY = "your-sensor-api-key"  # Depuis config.py
$BASE_URL = "http://localhost:8000"
```

---

## 4.2 Tests Health Check

```powershell
# Test 1: Vérifier que l'API est en ligne
curl -X GET "$BASE_URL/health"
# Attendu: {"status":"healthy","services":{"firebase":"connected",...}}

# Test 2: Infos API
curl -X GET "$BASE_URL/api/v1/info"
# Attendu: {"name":"AeroPark Smart System API","version":"1.0.0",...}
```

---

## 4.3 Tests Parking (Public)

```powershell
# Test 3: État du parking
curl -X GET "$BASE_URL/parking/status"
# Attendu: {"total":6,"free":4,"reserved":1,"occupied":1,"places":[...]}

# Test 4: Places disponibles
curl -X GET "$BASE_URL/parking/available"
# Attendu: {"available":[...],"count":4}

# Test 5: Détails d'une place
curl -X GET "$BASE_URL/parking/place/a1"
# Attendu: {"id":"a1","etat":"free",...}
```

---

## 4.4 Tests Réservation (Authentifié)

```powershell
# Test 6: Réserver une place
curl -X POST "$BASE_URL/parking/reserve" `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{
    "place_id": "a1",
    "duration_minutes": 120,
    "vehicle_plate": "CD-123-GO"
  }'
# Attendu: {"success":true,"reservation":{...},"access_code":"ABC"}

# Test 7: Ma réservation active
curl -X GET "$BASE_URL/users/me/reservation" `
  -H "Authorization: Bearer $TOKEN"
# Attendu: {"has_reservation":true,"reservation":{...}}
```

---

## 4.5 Tests Profil Utilisateur

```powershell
# Test 8: Mon profil
curl -X GET "$BASE_URL/users/me" `
  -H "Authorization: Bearer $TOKEN"
# Attendu: {"profile":{"uid":"...","email":"...","role":"user"},...}

# Test 9: Mettre à jour profil
curl -X PUT "$BASE_URL/users/me/profile?display_name=Jean&vehicle_plate=AB-123" `
  -H "Authorization: Bearer $TOKEN"
# Attendu: {"success":true}
```

---

## 4.6 Tests Codes d'Accès (Capteur/ESP32)

```powershell
# Test 10: Valider code à l'entrée
curl -X POST "$BASE_URL/api/v1/access/validate-code" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "code": "ABC",
    "sensor_presence": true,
    "barrier_id": "entry"
  }'
# Attendu (code valide): {"access_granted":true,"message":"Accès autorisé","place_id":"a1"}
# Attendu (code invalide): {"access_granted":false,"message":"Code invalide"}

# Test 11: Vérifier accès entrée (auto)
curl -X POST "$BASE_URL/api/v1/access/check-entry?sensor_presence=true" `
  -H "X-API-Key: $API_KEY"
# Attendu (places libres): {"access_granted":true,"reason":"places_available"}
# Attendu (parking plein): {"access_granted":false,"message":"Parking complet - code requis"}
```

---

## 4.7 Tests Barrière

```powershell
# Test 12: Statut barrière
curl -X GET "$BASE_URL/api/v1/barrier/status?barrier_id=entry" `
  -H "X-API-Key: $API_KEY"
# Attendu: {"barrier_id":"entry","status":"closed","parking_available_spots":4,...}

# Test 13: Ouvrir barrière (manuel)
curl -X POST "$BASE_URL/api/v1/barrier/open" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"barrier_id":"entry","reason":"manual"}'
# Attendu: {"success":true,"action":"opened","open_duration_seconds":30}
```

---

## 4.8 Tests Paiement

```powershell
# Test 14: Tarification
curl -X GET "$BASE_URL/api/v1/payment/pricing"
# Attendu: {"hourly_rate":5.0,"daily_max":50.0,"first_minutes_free":15,...}

# Test 15: Calculer montant
curl -X POST "$BASE_URL/api/v1/payment/calculate?hours=2&minutes=30"
# Attendu: {"duration_hours":2.5,"amount":12.50,...}

# Test 16: Simuler paiement Orange Money
curl -X POST "$BASE_URL/api/v1/payment/simulate" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "place_id": "a1",
    "duration_minutes": 120,
    "method": "ORANGE_MONEY",
    "simulate_failure": false
  }'
# Attendu: {"success":true,"payment_id":"...","status":"completed","access_code":"XYZ"}
```

---

## 4.9 Tests Capteur (ESP32)

```powershell
# Test 17: Mise à jour capteur - Véhicule détecté
curl -X POST "$BASE_URL/api/v1/sensor/update" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "sensor_id": "sensor_a1",
    "place_id": "a1",
    "presence": true
  }'
# Attendu: {"success":true,"place_id":"a1","new_status":"occupied"}

# Test 18: Mise à jour capteur - Véhicule parti
curl -X POST "$BASE_URL/api/v1/sensor/update" `
  -H "X-API-Key: $API_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "sensor_id": "sensor_a1",
    "place_id": "a1",
    "presence": false
  }'
# Attendu: {"success":true,"place_id":"a1","new_status":"free"}
```

---

## 4.10 Tests Admin

```powershell
# Test 19: Statistiques admin
curl -X GET "$BASE_URL/admin/parking/stats" `
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Attendu: {"total_places":6,"libres":4,"occupees":1,"reservees":1,"taux_occupation":33.33}

# Test 20: Toutes les places (admin)
curl -X GET "$BASE_URL/admin/parking/all" `
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Attendu: {"total":6,"places":[...],"admin":"admin@aeropark.com"}

# Test 21: Forcer libération
curl -X POST "$BASE_URL/admin/parking/force-release/a1?reason=maintenance" `
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Attendu: {"success":true,"message":"Place a1 libérée"}

# Test 22: Tous les codes d'accès
curl -X GET "$BASE_URL/admin/parking/access-codes" `
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Attendu: {"total":5,"codes":[...],"admin":"admin@aeropark.com"}

# Test 23: Invalider code
curl -X POST "$BASE_URL/admin/parking/access-codes/ABC/invalidate" `
  -H "Authorization: Bearer $ADMIN_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"reason":"test invalidation"}'
# Attendu: {"success":true}
```

---

# 5. CHECKLIST DE DÉBOGAGE

## 5.1 Si la Réservation Échoue

| Vérifier | Comment | Solution |
|----------|---------|----------|
| Token valide | Console > localStorage > `aeropark_token` | Re-login |
| Token non expiré | Décoder JWT sur jwt.io | Re-login |
| Place disponible | API `/parking/place/{id}` | Choisir autre place |
| Backend en ligne | `curl http://localhost:8000/health` | Redémarrer uvicorn |
| CORS | Console > Erreur CORS | Vérifier `config.py` CORS_ORIGINS |
| Format requête | Network tab > Request payload | Vérifier JSON |

---

## 5.2 Si le Paiement Échoue

| Vérifier | Comment | Solution |
|----------|---------|----------|
| Méthode supportée | ORANGE_MONEY, AIRTEL_MONEY, MPESA | Vérifier nom méthode |
| Format téléphone | +243XXXXXXXXX | Format valide |
| Réservation existe | `/users/me/reservation` | Créer réservation d'abord |
| Simulation d'échec | `simulate_failure: false` | Mettre false |
| Clé API | Header X-API-Key | Vérifier config.py |

---

## 5.3 Si la Barrière Ne S'ouvre Pas

| Vérifier | Comment | Solution |
|----------|---------|----------|
| Code valide | API `/api/v1/access/validate-code` | Générer nouveau code |
| Code non expiré | Vérifier `expires_at` | Générer nouveau code |
| Code non utilisé | Vérifier `status` | Générer nouveau code |
| Présence véhicule | `sensor_presence: true` | Capteur doit détecter |
| Clé API ESP32 | Header X-API-Key | Vérifier dans ESP32 |
| Places disponibles | `/parking/status` | Si plein, code requis |

---

## 5.4 Si l'Accès Admin Est Refusé

| Vérifier | Comment | Solution |
|----------|---------|----------|
| Rôle dans Firestore | Collection `users` > document UID | Ajouter `role: "admin"` |
| Token contient rôle | Décoder JWT | Re-login après modification |
| Endpoint correct | `/admin/parking/*` | Pas `/admin/*` |
| Token présent | Header `Authorization: Bearer ...` | Ajouter header |

---

## 5.5 Si le Token Est Invalide

| Vérifier | Comment | Solution |
|----------|---------|----------|
| Token présent | localStorage.getItem('aeropark_token') | Re-login |
| Format Bearer | `Authorization: Bearer TOKEN` | Ajouter "Bearer " |
| Firebase config | `auth.js` firebaseConfig | Vérifier API keys |
| Token expiré | jwt.io > exp claim | Re-login (token refresh) |

---

## 5.6 Si les Données Ne Chargent Pas

| Vérifier | Comment | Solution |
|----------|---------|----------|
| Console errors | F12 > Console | Lire erreur |
| Network requests | F12 > Network | Vérifier status codes |
| CORS | Console > CORS error | Backend CORS config |
| API_BASE_URL | `api.js` ligne 14 | `http://localhost:8000` |
| Backend running | Terminal | Vérifier uvicorn |

---

# 6. VÉRIFICATION FRONTEND

## 6.1 États Visuels des Places

| État | Couleur | Icône | Classe CSS | API `etat` |
|------|---------|-------|------------|------------|
| Libre | 🟢 Vert | ✓ | `.free`, `.status-dot.online` | `"free"` |
| Réservée | 🟡 Jaune | ⏳ | `.reserved`, `.status-dot.pending` | `"reserved"` |
| Occupée | 🔴 Rouge | ✗ | `.occupied`, `.status-dot.offline` | `"occupied"` |

---

## 6.2 Transitions d'État Attendues

```
SCÉNARIO COMPLET:

1. Place libre (🟢 free)
        ↓ [Utilisateur réserve]
2. Place réservée (🟡 reserved)
        ↓ [Véhicule entre + code validé]
3. Place occupée (🔴 occupied)
        ↓ [Véhicule sort]
4. Place libre (🟢 free)
```

---

## 6.3 Comportements UI à Vérifier

### Page Accueil
- [ ] Grille parking affiche toutes les places
- [ ] Compteurs mis à jour en temps réel
- [ ] Clic sur place libre → Modal réservation
- [ ] Clic sur place occupée → Rien / info

### Page Dashboard User
- [ ] Statistiques personnelles affichées
- [ ] Réservation active visible
- [ ] Bouton "Code d'Accès" fonctionne
- [ ] Compte à rebours temps restant

### Page Réservations
- [ ] Liste toutes les réservations
- [ ] Filtres fonctionnent (statut, date)
- [ ] Bouton Annuler (si à venir)
- [ ] Bouton Prolonger (si actif)

### Page Codes d'Accès
- [ ] Dropdown réservations peuplé
- [ ] Génération code fonctionne
- [ ] Code affiché en grand
- [ ] Compte à rebours expiration
- [ ] Bouton copier fonctionne

### Page Paiements
- [ ] Paiements en attente listés
- [ ] Sélection méthode (Orange/Airtel/M-Pesa)
- [ ] Champ téléphone apparaît
- [ ] Historique paiements affiché

### Navigation Mobile
- [ ] Menu hamburger fonctionne
- [ ] Menu se ferme après clic
- [ ] Liens corrects

---

## 6.4 Messages Toast Attendus

| Action | Toast Succès | Toast Erreur |
|--------|--------------|--------------|
| Login | "Connexion Réussie" | "Identifiants incorrects" |
| Register | "Compte Créé" | "Email déjà utilisé" |
| Réservation | "Réservation Confirmée" | "Place non disponible" |
| Paiement | "Paiement effectué" | "Échec du paiement" |
| Annulation | "Réservation annulée" | "Impossible d'annuler" |
| Code généré | "Code généré avec succès" | "Échec de génération" |
| Déconnexion | "Déconnexion réussie" | - |

---

# 7. TESTS ESP32/CAPTEURS

## 7.1 Simulation Capteur (Sans Matériel)

```powershell
# Simuler détection véhicule sur place a1
curl -X POST "http://localhost:8000/api/v1/sensor/update" `
  -H "X-API-Key: YOUR_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"sensor_id":"sensor_a1","place_id":"a1","presence":true}'

# Simuler départ véhicule
curl -X POST "http://localhost:8000/api/v1/sensor/update" `
  -H "X-API-Key: YOUR_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"sensor_id":"sensor_a1","place_id":"a1","presence":false}'
```

---

## 7.2 Test Flux Complet ESP32

### Scénario: Entrée avec Places Libres

```
1. ESP32 détecte véhicule à l'entrée
   → POST /api/v1/access/check-entry?sensor_presence=true
   
2. Backend répond: access_granted=true (places libres)
   
3. ESP32 ouvre barrière
   → POST /api/v1/barrier/open (reason="auto_free")
   
4. Véhicule entre, se gare sur place a1
   
5. Capteur a1 détecte présence
   → POST /api/v1/sensor/update (place_id=a1, presence=true)
   
6. Place a1 devient "occupied"
```

### Scénario: Entrée avec Code (Parking Plein)

```
1. ESP32 détecte véhicule à l'entrée
   → POST /api/v1/access/check-entry?sensor_presence=true
   
2. Backend répond: access_granted=false (parking plein)
   
3. Utilisateur entre code "ABC"
   → POST /api/v1/access/validate-code (code="ABC")
   
4. Backend répond: access_granted=true, place_id="a2"
   
5. ESP32 ouvre barrière
   
6. Véhicule se gare sur a2
   
7. Place a2 → "occupied"
```

### Scénario: Sortie

```
1. Capteur a1 ne détecte plus véhicule
   → POST /api/v1/sensor/update (place_id=a1, presence=false)
   
2. Place a1 → "free" (si réservation terminée)
   OU → "reserved" (si réservation encore active)
   
3. Véhicule arrive à barrière sortie
   
4. ESP32 détecte présence
   → POST /api/v1/access/exit?sensor_presence=true
   
5. Barrière s'ouvre automatiquement
```

---

## 7.3 Vérification WebSocket (Temps Réel)

```javascript
// Ouvrir dans la console du navigateur
const ws = new WebSocket('ws://localhost:8000/ws/parking');

ws.onopen = () => console.log('WebSocket connecté');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Mise à jour reçue:', data);
};

ws.onerror = (error) => console.error('Erreur WS:', error);
```

**Test:** Changer état d'une place via curl, vérifier que le message arrive.

---

# 8. RÉSUMÉ DES TESTS

## Checklist Finale Avant Production

### Backend
- [ ] Health check OK
- [ ] Tous les endpoints répondent
- [ ] Firebase connecté
- [ ] Scheduler actif
- [ ] WebSocket fonctionnel

### Frontend - Public
- [ ] Page accueil charge
- [ ] Login fonctionne
- [ ] Register fonctionne
- [ ] État parking visible

### Frontend - User
- [ ] Dashboard charge
- [ ] Réservation fonctionne
- [ ] Codes d'accès générés
- [ ] Paiements fonctionnent
- [ ] Annulation fonctionne

### Frontend - Admin
- [ ] Accès admin OK
- [ ] Stats affichées
- [ ] Force release OK
- [ ] Liste codes OK
- [ ] Liste paiements OK

### Intégration ESP32
- [ ] Capteurs envoient données
- [ ] Barrière répond aux commandes
- [ ] Codes validés correctement
- [ ] Transitions d'état correctes

### Mobile/PWA
- [ ] Responsive OK
- [ ] Menu hamburger OK
- [ ] PWA installable
- [ ] Mode hors ligne basique

---

**Document généré le:** 26 janvier 2026
**Version:** 1.0
**Projet:** AeroPark GOMA - Système de Parking Intelligent
