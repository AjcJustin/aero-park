/*
 * =============================================================================
 * AEROPARK SMART SYSTEM - Code ESP32
 * Système de Gestion de Parking Intelligent pour Aéroport
 * =============================================================================
 * 
 * MATÉRIEL UTILISÉ:
 * - ESP32 DevKit
 * - 6 Capteurs IR (un par place de parking a1-a6)
 * - 2 Capteurs IR (entrée/sortie)
 * - 1 Servo moteur (barrière)
 * - 1 Écran LCD I2C 16x2
 * 
 * CONNEXIONS:
 * - Capteurs places: GPIO 13, 14, 25, 26, 27, 34
 * - Capteur entrée: GPIO 32
 * - Capteur sortie: GPIO 33
 * - Servo barrière: GPIO 4
 * - LCD: SDA=21, SCL=22
 * 
 * =============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// =============================================================================
// CONFIGURATION WIFI & SERVEUR
// =============================================================================
const char* ssid = "VOTRE_SSID";           // À MODIFIER
const char* password = "VOTRE_MOT_DE_PASSE"; // À MODIFIER

// Adresse IP du serveur backend (à modifier selon votre configuration)
const char* serverHost = "192.168.1.100";  // À MODIFIER
const int serverPort = 8000;

// URLs des endpoints
String serverUrl = "http://" + String(serverHost) + ":" + String(serverPort) + "/api/v1/sensor/update";
String healthUrl = "http://" + String(serverHost) + ":" + String(serverPort) + "/api/v1/sensor/health";

// Clé API (doit correspondre à SENSOR_API_KEY dans le backend .env)
const char* apiKey = "aeropark-sensor-key-2024";

// =============================================================================
// CONFIGURATION MATÉRIELLE
// =============================================================================

// Pins des capteurs IR pour chaque place (a1 à a6)
const int IR_PINS[6] = {13, 14, 25, 26, 27, 34};

// Pins capteurs entrée/sortie
const int IR_ENTREE = 32;
const int IR_SORTIE = 33;

// Pin du servo moteur
const int SERVO_PIN = 4;

// Nombre total de places
const int NB_PLACES = 6;

// =============================================================================
// OBJETS GLOBAUX
// =============================================================================

// Servo pour la barrière
Servo barriere;

// Écran LCD I2C (adresse 0x27, 16 colonnes, 2 lignes)
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Client WebSocket
WebSocketsClient webSocket;

// =============================================================================
// VARIABLES D'ÉTAT
// =============================================================================

// État précédent des places (pour détecter les changements)
bool etatPrecedent[6] = {false, false, false, false, false, false};

// Place réservée (-1 = aucune réservation active)
int placeReservee = -1;

// Timer pour les mises à jour périodiques
unsigned long dernierEnvoi = 0;
const unsigned long INTERVALLE_ENVOI = 5000; // 5 secondes

// Timer pour le health check
unsigned long dernierHealthCheck = 0;
const unsigned long INTERVALLE_HEALTH = 30000; // 30 secondes

// État de la connexion
bool wifiConnecte = false;
bool wsConnecte = false;

// =============================================================================
// INITIALISATION
// =============================================================================

void setup() {
    Serial.begin(115200);
    Serial.println("\n=== AEROPARK SMART SYSTEM ===");
    Serial.println("Initialisation...\n");

    // Initialisation des pins capteurs
    for (int i = 0; i < NB_PLACES; i++) {
        pinMode(IR_PINS[i], INPUT);
    }
    pinMode(IR_ENTREE, INPUT);
    pinMode(IR_SORTIE, INPUT);

    // Initialisation du servo
    barriere.attach(SERVO_PIN);
    fermerBarriere();

    // Initialisation du LCD
    lcd.init();
    lcd.backlight();
    afficherMessage("AeroPark", "Demarrage...");

    // Connexion WiFi
    connecterWiFi();

    // Connexion WebSocket
    if (wifiConnecte) {
        setupWebSocket();
    }

    // Premier envoi de l'état
    envoyerToutesLesPlaces();

    Serial.println("Système prêt!\n");
    afficherPlacesDisponibles();
}

// =============================================================================
// CONNEXION WIFI
// =============================================================================

void connecterWiFi() {
    Serial.print("Connexion WiFi à ");
    Serial.println(ssid);
    afficherMessage("WiFi...", ssid);

    WiFi.begin(ssid, password);

    int tentatives = 0;
    while (WiFi.status() != WL_CONNECTED && tentatives < 20) {
        delay(500);
        Serial.print(".");
        tentatives++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        wifiConnecte = true;
        Serial.println("\nWiFi connecté!");
        Serial.print("Adresse IP: ");
        Serial.println(WiFi.localIP());
        afficherMessage("WiFi OK", WiFi.localIP().toString().c_str());
        delay(1000);
    } else {
        wifiConnecte = false;
        Serial.println("\nÉchec connexion WiFi!");
        afficherMessage("WiFi ERREUR", "Verifier config");
    }
}

// =============================================================================
// CONFIGURATION WEBSOCKET
// =============================================================================

void setupWebSocket() {
    Serial.println("Configuration WebSocket...");
    
    // Connexion au serveur WebSocket
    webSocket.begin(serverHost, serverPort, "/ws/parking");
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    
    Serial.println("WebSocket configuré");
}

// Gestionnaire d'événements WebSocket
void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
    switch (type) {
        case WStype_DISCONNECTED:
            wsConnecte = false;
            Serial.println("[WS] Déconnecté");
            break;

        case WStype_CONNECTED:
            wsConnecte = true;
            Serial.println("[WS] Connecté au serveur");
            break;

        case WStype_TEXT:
            Serial.print("[WS] Message reçu: ");
            Serial.println((char*)payload);
            traiterMessageWS((char*)payload);
            break;

        case WStype_ERROR:
            Serial.println("[WS] Erreur");
            break;

        default:
            break;
    }
}

// Traitement des messages WebSocket reçus
void traiterMessageWS(char* payload) {
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
        Serial.print("[WS] Erreur parsing JSON: ");
        Serial.println(error.c_str());
        return;
    }

    const char* type = doc["type"];

    // Message de réservation
    if (strcmp(type, "reservation") == 0) {
        JsonObject donnees = doc["donnees"];
        int placeId = donnees["place_id"];
        const char* action = donnees["action"];

        Serial.printf("[WS] Réservation - Place: %d, Action: %s\n", placeId, action);

        if (strcmp(action, "create") == 0) {
            // Nouvelle réservation
            placeReservee = placeId;
            afficherReservation(placeId);
            
            // Vérifier si véhicule à l'entrée
            if (vehiculeDetecteEntree()) {
                ouvrirBarriere();
                delay(3000);
                fermerBarriere();
            }
        } else if (strcmp(action, "cancel") == 0) {
            // Annulation de réservation
            if (placeReservee == placeId) {
                placeReservee = -1;
                afficherPlacesDisponibles();
            }
        }
    }
    // Message de connexion
    else if (strcmp(type, "connected") == 0) {
        Serial.println("[WS] Message de bienvenue reçu");
    }
}

// =============================================================================
// ENVOI HTTP AU SERVEUR
// =============================================================================

bool envoyerEtatPlace(int placeIndex, bool occupe) {
    if (!wifiConnecte || WiFi.status() != WL_CONNECTED) {
        Serial.println("[HTTP] Pas de connexion WiFi");
        return false;
    }

    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", apiKey);

    // Créer le JSON
    StaticJsonDocument<200> doc;
    doc["place_id"] = "a" + String(placeIndex + 1);  // a1, a2, etc.
    doc["etat"] = occupe ? "occupied" : "free";
    doc["force_signal"] = WiFi.RSSI();

    String jsonString;
    serializeJson(doc, jsonString);

    Serial.print("[HTTP] Envoi: ");
    Serial.println(jsonString);

    int httpCode = http.POST(jsonString);

    if (httpCode > 0) {
        String response = http.getString();
        Serial.printf("[HTTP] Code: %d, Réponse: %s\n", httpCode, response.c_str());
        http.end();
        return (httpCode == 200);
    } else {
        Serial.printf("[HTTP] Erreur: %s\n", http.errorToString(httpCode).c_str());
        http.end();
        return false;
    }
}

void envoyerToutesLesPlaces() {
    Serial.println("\n[HTTP] Envoi état de toutes les places...");
    for (int i = 0; i < NB_PLACES; i++) {
        bool occupe = digitalRead(IR_PINS[i]) == LOW;  // LOW = obstacle détecté
        envoyerEtatPlace(i, occupe);
        etatPrecedent[i] = occupe;
        delay(100);  // Petit délai entre les envois
    }
}

void verifierHealthCheck() {
    if (!wifiConnecte || WiFi.status() != WL_CONNECTED) return;

    HTTPClient http;
    http.begin(healthUrl);
    http.addHeader("X-API-Key", apiKey);

    int httpCode = http.GET();

    if (httpCode == 200) {
        Serial.println("[HEALTH] Serveur OK");
    } else {
        Serial.printf("[HEALTH] Erreur serveur: %d\n", httpCode);
    }

    http.end();
}

// =============================================================================
// DÉTECTION VÉHICULES
// =============================================================================

bool vehiculeDetecteEntree() {
    return digitalRead(IR_ENTREE) == LOW;
}

bool vehiculeDetecteSortie() {
    return digitalRead(IR_SORTIE) == LOW;
}

// =============================================================================
// CONTRÔLE BARRIÈRE
// =============================================================================

void ouvrirBarriere() {
    Serial.println("[BARRIERE] Ouverture");
    barriere.write(90);  // Position ouverte
}

void fermerBarriere() {
    Serial.println("[BARRIERE] Fermeture");
    barriere.write(0);   // Position fermée
}

// =============================================================================
// AFFICHAGE LCD
// =============================================================================

void afficherMessage(const char* ligne1, const char* ligne2) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(ligne1);
    lcd.setCursor(0, 1);
    lcd.print(ligne2);
}

void afficherPlacesDisponibles() {
    int placesLibres = 0;
    for (int i = 0; i < NB_PLACES; i++) {
        if (digitalRead(IR_PINS[i]) == HIGH) {
            placesLibres++;
        }
    }

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("AeroPark");
    lcd.setCursor(0, 1);
    lcd.print("Libres: ");
    lcd.print(placesLibres);
    lcd.print("/");
    lcd.print(NB_PLACES);
}

void afficherReservation(int placeId) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("RESERVATION");
    lcd.setCursor(0, 1);
    lcd.print("Place: A");
    lcd.print(placeId);
}

// =============================================================================
// COMPTAGE DE PLACES
// =============================================================================

int compterPlacesLibres() {
    int count = 0;
    for (int i = 0; i < NB_PLACES; i++) {
        if (digitalRead(IR_PINS[i]) == HIGH) {  // HIGH = pas d'obstacle = libre
            count++;
        }
    }
    return count;
}

// =============================================================================
// BOUCLE PRINCIPALE
// =============================================================================

void loop() {
    // Maintenir la connexion WebSocket
    if (wifiConnecte) {
        webSocket.loop();
    }

    // Vérifier les changements d'état des places
    for (int i = 0; i < NB_PLACES; i++) {
        bool occupe = digitalRead(IR_PINS[i]) == LOW;

        // Si l'état a changé
        if (occupe != etatPrecedent[i]) {
            Serial.printf("[PLACE] A%d: %s\n", i + 1, occupe ? "OCCUPÉE" : "LIBRE");
            
            // Envoyer la mise à jour au serveur
            envoyerEtatPlace(i, occupe);
            etatPrecedent[i] = occupe;

            // Mettre à jour l'affichage
            afficherPlacesDisponibles();
        }
    }

    // Vérifier entrée véhicule
    if (vehiculeDetecteEntree()) {
        if (placeReservee > 0) {
            // Véhicule avec réservation
            Serial.println("[ENTREE] Véhicule détecté - Réservation active");
            ouvrirBarriere();
            delay(3000);
            fermerBarriere();
            placeReservee = -1;  // Réservation utilisée
        } else if (compterPlacesLibres() > 0) {
            // Places disponibles sans réservation
            Serial.println("[ENTREE] Véhicule détecté - Places disponibles");
            ouvrirBarriere();
            delay(3000);
            fermerBarriere();
        } else {
            Serial.println("[ENTREE] Véhicule détecté - Parking COMPLET");
            afficherMessage("PARKING", "COMPLET");
            delay(2000);
            afficherPlacesDisponibles();
        }
        delay(1000);  // Éviter les détections multiples
    }

    // Vérifier sortie véhicule
    if (vehiculeDetecteSortie()) {
        Serial.println("[SORTIE] Véhicule détecté");
        ouvrirBarriere();
        delay(3000);
        fermerBarriere();
        delay(1000);  // Éviter les détections multiples
    }

    // Health check périodique
    unsigned long maintenant = millis();
    if (maintenant - dernierHealthCheck >= INTERVALLE_HEALTH) {
        verifierHealthCheck();
        dernierHealthCheck = maintenant;
    }

    // Petite pause
    delay(100);
}
