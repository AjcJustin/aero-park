// =============================================================================
// AEROPARK SMART SYSTEM - ESP32 UPDATED (FIXED)
// LCD 20x4 + Capteurs + Barriere + Backend + WebSocket Real-time
// FIX: Détection correcte du départ de voiture (RESERVE -> FREE)
// =============================================================================
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// =============================================================================
// WIFI & BACKEND
// =============================================================================
const char* ssid = "globaltech";
const char* password = "Akim1234@@";
const char* serverHost = "192.168.1.141";
const int serverPort = 8000;
const char* apiKey = "aeropark-sensor-key-2024";

// URLs API
String parkingInfoUrl = "http://" + String(serverHost) + ":" + String(serverPort) + "/api/v1/barrier/parking-info";
String sensorUpdateUrl = "http://" + String(serverHost) + ":" + String(serverPort) + "/api/v1/sensor/update";
String parkingStatusUrl = "http://" + String(serverHost) + ":" + String(serverPort) + "/parking/status";

// =============================================================================
// CONFIGURATION MATÉRIELLE
// =============================================================================
#define NB_PLACES 6
const int IR_PINS[NB_PLACES] = {13, 14, 25, 26, 27, 19};
const int IR_ENTREE = 32;
const int IR_SORTIE = 33;
const int SERVO_PIN = 4;

// =============================================================================
// OBJETS
// =============================================================================
Servo barriere;
LiquidCrystal_I2C lcd(0x27, 20, 4);
WebSocketsClient webSocket;

// =============================================================================
// VARIABLES
// =============================================================================
bool wifiConnecte = false;
bool systemReady = false;
bool codeValidatedViaWeb = false;
unsigned long codeValidationTime = 0;
const unsigned long VALIDATION_TIMEOUT = 60000; // 1 minute pour entrer

enum PlaceEtat { LIBRE, OCCUPE, RESERVE };
PlaceEtat etatPlaces[NB_PLACES];

// =============================================================================
// OUTILS LCD
// =============================================================================
const char* etatToText(PlaceEtat etat) {
  switch (etat) {
    case LIBRE: return "Libre";
    case OCCUPE: return "Occupe";
    case RESERVE: return "Reserve";
    default: return "----";
  }
}

void afficherLCD() {
  int libres = 0;
  for (int i = 0; i < NB_PLACES; i++) {
    if (etatPlaces[i] == LIBRE) libres++;
  }

  lcd.clear();
  if (libres == 0) {
    // Vérifier si il y a des reservations
    bool aDesReservations = false;
    for (int i=0; i<NB_PLACES; i++) if(etatPlaces[i] == RESERVE) aDesReservations = true;
    
    lcd.setCursor(3, 0);
    lcd.print("PARKING COMPLET");
    if (aDesReservations) {
        lcd.setCursor(0, 1);
        lcd.print("Acces par CODE seul");
    }
  } else {
    lcd.setCursor(0, 0);
    lcd.print("Libre:");
    lcd.print(libres);
    lcd.print("  Total:");
    lcd.print(NB_PLACES);
  }

  lcd.setCursor(0, 1);
  lcd.print("P1:"); lcd.print(etatToText(etatPlaces[0]));
  lcd.print(" P2:"); lcd.print(etatToText(etatPlaces[1]));

  lcd.setCursor(0, 2);
  lcd.print("P3:"); lcd.print(etatToText(etatPlaces[2]));
  lcd.print(" P4:"); lcd.print(etatToText(etatPlaces[3]));

  lcd.setCursor(0, 3);
  lcd.print("P5:"); lcd.print(etatToText(etatPlaces[4]));
  lcd.print(" P6:"); lcd.print(etatToText(etatPlaces[5]));
}

// =============================================================================
// WIFI
// =============================================================================
void connecterWiFi() {
  Serial.println("Connexion WiFi...");
  WiFi.begin(ssid, password);
  int essais = 0;
  while (WiFi.status() != WL_CONNECTED && essais < 20) {
    delay(500);
    essais++;
  }
  wifiConnecte = WiFi.status() == WL_CONNECTED;
  Serial.println(wifiConnecte ? "WiFi Connecte" : "WiFi Erreur");
}

// =============================================================================
// Mise à jour de l'état local depuis JSON
// =============================================================================
void updatePlacesFromJSON(JsonArray places) {
    for (int i = 0; i < NB_PLACES && i < places.size(); i++) {
      const char* etat = places[i]["etat"];
      if (!etat) etat = places[i]["status"]; // Supporte "etat" ou "status"
      
      if (strcmp(etat, "free") == 0) etatPlaces[i] = LIBRE;
      else if (strcmp(etat, "reserved") == 0) etatPlaces[i] = RESERVE;
      else etatPlaces[i] = OCCUPE;
    }
    afficherLCD();
}

void recupererEtatParking() {
  if (!wifiConnecte) return;
  HTTPClient http;
  http.begin(parkingStatusUrl);
  http.addHeader("X-API-Key", apiKey);
  int code = http.GET();
  if (code == 200) {
    StaticJsonDocument<4096> doc;
    deserializeJson(doc, http.getString());
    updatePlacesFromJSON(doc["places"].as<JsonArray>());
  }
  http.end();
}

// =============================================================================
// WEBSOCKET
// =============================================================================
void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  if (type == WStype_TEXT) {
    StaticJsonDocument<4096> doc;
    if (deserializeJson(doc, payload)) return;

    if (strcmp(doc["type"], "parking_update") == 0) {
      Serial.println("WS: Mise à jour parking reçue");
      updatePlacesFromJSON(doc["places"].as<JsonArray>());
    } 
    else if (strcmp(doc["type"], "code_validated") == 0) {
      Serial.println("WS: Code validé via Web ! Prêt pour ouverture.");
      codeValidatedViaWeb = true;
      codeValidationTime = millis();
    }
  }
}

void setupWebSocket() {
  webSocket.begin(serverHost, serverPort, "/ws/parking");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
}

// =============================================================================
// CAPTEURS
// =============================================================================
bool envoyerEtatPlace(int index, bool occupe) {
  if (!wifiConnecte) return false;
  HTTPClient http;
  http.begin(sensorUpdateUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);

  StaticJsonDocument<256> doc;
  doc["place_id"] = "a" + String(index + 1);
  doc["etat"] = occupe ? "occupied" : "free";

  String body;
  serializeJson(doc, body);

  int code = http.POST(body);
  http.end();
  return code == 200;
}

// =============================================================================
// BARRIERE
// =============================================================================
#define SERVO_FERME 0
#define SERVO_OUVERT 90

void ouvrirBarriere() { barriere.write(SERVO_OUVERT); }
void fermerBarriere() { barriere.write(SERVO_FERME); }

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < NB_PLACES; i++) {
    pinMode(IR_PINS[i], INPUT_PULLUP);
    etatPlaces[i] = LIBRE;
  }

  pinMode(IR_ENTREE, INPUT_PULLUP);
  pinMode(IR_SORTIE, INPUT_PULLUP);

  barriere.attach(SERVO_PIN);
  fermerBarriere();

  lcd.init();
  lcd.backlight();
  lcd.print("AeroPark Demarrage");

  connecterWiFi();
  if (wifiConnecte) {
      setupWebSocket();
      recupererEtatParking();
  }

  systemReady = true;
}

void loop() {
  if (wifiConnecte) webSocket.loop();

  // 1. GESTION DES CAPTEURS DE PLACES (Real-time local)
  // FIX CRITIQUE: Changé de "etatPlaces[i] == OCCUPE" à "etatPlaces[i] != LIBRE"
  // Cela permet de détecter le départ même si la place était RESERVE
  for (int i = 0; i < NB_PLACES; i++) {
    bool detecte = digitalRead(IR_PINS[i]) == LOW;
    
    if (detecte && etatPlaces[i] != OCCUPE) {
        // Voiture détectée et place n'était pas occupée
        etatPlaces[i] = OCCUPE;
        envoyerEtatPlace(i, true);
        afficherLCD();
        Serial.print("Place ");
        Serial.print(i+1);
        Serial.println(" -> OCCUPE");
    } 
    else if (!detecte && etatPlaces[i] != LIBRE) {
        // ← FIX: Voiture partie, peu importe si place était OCCUPE ou RESERVE
        etatPlaces[i] = LIBRE;
        envoyerEtatPlace(i, false);
        afficherLCD();
        Serial.print("Place ");
        Serial.print(i+1);
        Serial.println(" -> LIBRE");
    }
  }

  // 2. LOGIQUE ENTRÉE
  if (systemReady && digitalRead(IR_ENTREE) == LOW) {
    int libres = 0;
    for (int i = 0; i < NB_PLACES; i++) if (etatPlaces[i] == LIBRE) libres++;
    bool autorise = false;
    
    // Cas A: Il y a des places
    if (libres > 0) {
        Serial.println("Entree libre autorisee");
        autorise = true;
    } 
    // Cas B: Parking plein mais code validé via App
    else if (codeValidatedViaWeb) {
        if (millis() - codeValidationTime < VALIDATION_TIMEOUT) {
            Serial.println("Entree reservee autorisee (Code App)");
            autorise = true;
        } else {
            Serial.println("Code App expire");
            codeValidatedViaWeb = false;
        }
    }

    if (autorise) {
      ouvrirBarriere();
      delay(5000);
      fermerBarriere();
      codeValidatedViaWeb = false; // Reset après passage
      afficherLCD();
    }
  }

  // 3. LOGIQUE SORTIE
  if (systemReady && digitalRead(IR_SORTIE) == LOW) {
    ouvrirBarriere();
    delay(5000);
    fermerBarriere();
    afficherLCD();
  }

  delay(100);
}
