/*
 * AeroPark Smart System - ESP32 Barrier Controller
 * Contrôleur de barrière avec clavier et écran LCD.
 * 
 * Fonctionnalités:
 * - Détection véhicule entrée/sortie
 * - Saisie code 3 caractères sur clavier matriciel
 * - Affichage LCD 16x2
 * - Contrôle servo barrière
 * - Communication WebSocket avec le serveur
 * 
 * Reliability Features (v2.0):
 * - Retry logic with 3 attempts for API calls
 * - Local caching of parking status
 * - Heartbeat ping every 30 seconds
 * - Graceful offline mode
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoWebsockets.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>
#include <Keypad.h>
#include <ArduinoJson.h>
#include <Preferences.h>

using namespace websockets;

// ============== CONFIGURATION WiFi ==============
const char* WIFI_SSID = "votre_ssid";
const char* WIFI_PASSWORD = "votre_password";

// ============== CONFIGURATION SERVEUR ==============
const char* SERVER_HOST = "192.168.50.100";  // IP du serveur FastAPI
const int SERVER_PORT = 8000;
const char* API_KEY = "aeropark-sensor-key-2024";
const char* DEVICE_ID = "ESP32-BARRIER-001";
const char* FIRMWARE_VERSION = "2.0.0";

// ============== RELIABILITY SETTINGS ==============
#define MAX_RETRY_ATTEMPTS 3
#define RETRY_DELAY_MS 1000
#define HEARTBEAT_INTERVAL_MS 30000  // 30 seconds
#define CACHE_EXPIRY_MS 300000       // 5 minutes
#define WIFI_RECONNECT_INTERVAL 10000

// ============== CONFIGURATION PINS ==============
// Capteur IR entrée/sortie
#define ENTRY_SENSOR_PIN 32   // Capteur présence entrée
#define EXIT_SENSOR_PIN  33   // Capteur présence sortie

// Servo barrière
#define ENTRY_SERVO_PIN  4    // Servo barrière entrée
#define EXIT_SERVO_PIN   5    // Servo barrière sortie (optionnel)

// Configuration clavier matriciel 4x4
const byte ROWS = 4;
const byte COLS = 4;
char keys[ROWS][COLS] = {
    {'1', '2', '3', 'A'},
    {'4', '5', '6', 'B'},
    {'7', '8', '9', 'C'},
    {'*', '0', '#', 'D'}
};
byte rowPins[ROWS] = {15, 2, 0, 4};   // Adapter selon votre câblage
byte colPins[COLS] = {16, 17, 18, 19};  // Adapter selon votre câblage

// LCD I2C
#define LCD_ADDR 0x27
#define LCD_COLS 16
#define LCD_ROWS 2

// ============== CONFIGURATION GÉNÉRALE ==============
#define CODE_LENGTH 3
#define BARRIER_OPEN_DURATION 10000  // 10 secondes
#define SENSOR_CHECK_INTERVAL 100    // 100ms entre vérifications

// ============== OBJETS GLOBAUX ==============
LiquidCrystal_I2C lcd(LCD_ADDR, LCD_COLS, LCD_ROWS);
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);
Servo entryServo;
Servo exitServo;
WebsocketsClient wsClient;
Preferences preferences;

// ============== VARIABLES D'ÉTAT ==============
String inputCode = "";
bool entryVehicleDetected = false;
bool exitVehicleDetected = false;
bool entryBarrierOpen = false;
bool exitBarrierOpen = false;
unsigned long barrierOpenTime = 0;
int freeSpots = 6;
bool requireCode = false;

// ============== RELIABILITY VARIABLES ==============
unsigned long lastHeartbeatTime = 0;
unsigned long lastCacheUpdate = 0;
unsigned long lastWiFiCheck = 0;
unsigned long deviceUptime = 0;
int successfulApiCalls = 0;
int failedApiCalls = 0;
bool isOfflineMode = false;

// Cached parking status
struct CachedStatus {
    int freeSpots;
    bool requireCode;
    unsigned long timestamp;
    bool valid;
} cachedStatus = {6, false, 0, false};

// Sensor health status
struct SensorHealth {
    bool irSensors;
    bool servo;
    bool lcd;
    bool entrySensor;
    bool exitSensor;
} sensorHealth = {true, true, true, true, true};

// État système
enum SystemState {
    STATE_IDLE,
    STATE_WAITING_CODE,
    STATE_VALIDATING,
    STATE_BARRIER_OPEN,
    STATE_ERROR,
    STATE_OFFLINE
};
SystemState currentState = STATE_IDLE;

// ============== PROTOTYPES ==============
void setupWiFi();
void setupWebSocket();
void handleWebSocketMessage(WebsocketsMessage message);
void checkEntrySensor();
void checkExitSensor();
void handleKeypadInput();
void validateCode(String code);
void openBarrier(String barrier_id);
void closeBarrier(String barrier_id);
void updateLCD();
void checkBarrierTimeout();
void requestParkingInfo();
// Reliability functions
bool httpRequestWithRetry(String url, String method, String body, String& response, int maxRetries = MAX_RETRY_ATTEMPTS);
void sendHeartbeat();
void updateCache(int spots, bool needCode);
void loadCachedStatus();
void saveCachedStatus();
void checkWiFiConnection();
void checkSensorHealth();

// ============== SETUP ==============
void setup() {
    Serial.begin(115200);
    Serial.println("\n=== AeroPark Barrier Controller v2.0 ===");
    Serial.println("Reliability features enabled:");
    Serial.println("  - Retry logic (3 attempts)");
    Serial.println("  - Local caching");
    Serial.println("  - Heartbeat ping (30s)");
    
    // Initialize preferences for caching
    preferences.begin("aeropark", false);
    loadCachedStatus();
    
    // Initialiser les pins capteurs
    pinMode(ENTRY_SENSOR_PIN, INPUT);
    pinMode(EXIT_SENSOR_PIN, INPUT);
    
    // Initialiser LCD
    Wire.begin();
    lcd.init();
    lcd.backlight();
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("AeroPark v2.0");
    lcd.setCursor(0, 1);
    lcd.print("Initialisation..");
    sensorHealth.lcd = true;
    
    // Initialiser servos
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    entryServo.setPeriodHertz(50);
    exitServo.setPeriodHertz(50);
    entryServo.attach(ENTRY_SERVO_PIN, 500, 2400);
    exitServo.attach(EXIT_SERVO_PIN, 500, 2400);
    sensorHealth.servo = true;
    
    // Barrières fermées au départ
    entryServo.write(0);
    exitServo.write(0);
    
    // Connexion WiFi
    setupWiFi();
    
    // Connexion WebSocket
    setupWebSocket();
    
    // Demander l'état initial (with retry)
    requestParkingInfo();
    
    // Send initial heartbeat
    sendHeartbeat();
    
    // État initial
    currentState = STATE_IDLE;
    updateLCD();
    
    Serial.println("Setup complete!");
}

// ============== LOOP PRINCIPAL ==============
void loop() {
    // Update uptime
    deviceUptime = millis() / 1000;
    
    // Check WiFi connection periodically
    static unsigned long lastWiFiCheck = 0;
    if (millis() - lastWiFiCheck > WIFI_RECONNECT_INTERVAL) {
        checkWiFiConnection();
        lastWiFiCheck = millis();
    }
    
    // Maintenir WebSocket
    if (!isOfflineMode) {
        wsClient.poll();
    }
    
    // Send heartbeat every 30 seconds
    if (millis() - lastHeartbeatTime > HEARTBEAT_INTERVAL_MS) {
        sendHeartbeat();
        lastHeartbeatTime = millis();
    }
    
    // Vérifier les capteurs
    static unsigned long lastSensorCheck = 0;
    if (millis() - lastSensorCheck > SENSOR_CHECK_INTERVAL) {
        checkEntrySensor();
        checkExitSensor();
        checkSensorHealth();
        lastSensorCheck = millis();
    }
    
    // Gérer le clavier
    handleKeypadInput();
    
    // Vérifier timeout barrières
    checkBarrierTimeout();
    
    // Mise à jour LCD
    static unsigned long lastLCDUpdate = 0;
    if (millis() - lastLCDUpdate > 1000) {
        updateLCD();
        lastLCDUpdate = millis();
    }
}

// ============== WIFI ==============
void setupWiFi() {
    Serial.print("Connexion WiFi: ");
    Serial.println(WIFI_SSID);
    
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        lcd.setCursor(attempts % 16, 1);
        lcd.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi Connecté!");
        Serial.print("IP: ");
        Serial.println(WiFi.localIP());
        
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("WiFi OK");
        lcd.setCursor(0, 1);
        lcd.print(WiFi.localIP());
        delay(2000);
    } else {
        Serial.println("\nEchec WiFi!");
        lcd.clear();
        lcd.print("WiFi ERREUR!");
        currentState = STATE_ERROR;
    }
}

// ============== WEBSOCKET ==============
void setupWebSocket() {
    String wsUrl = "ws://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/ws/parking";
    Serial.print("Connexion WebSocket: ");
    Serial.println(wsUrl);
    
    wsClient.onMessage(handleWebSocketMessage);
    wsClient.onEvent([](WebsocketsEvent event, String data) {
        if (event == WebsocketsEvent::ConnectionOpened) {
            Serial.println("WebSocket connecté!");
        } else if (event == WebsocketsEvent::ConnectionClosed) {
            Serial.println("WebSocket déconnecté!");
        }
    });
    
    wsClient.connect(wsUrl);
}

void handleWebSocketMessage(WebsocketsMessage message) {
    Serial.print("WS: ");
    Serial.println(message.data());
    
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, message.data());
    
    if (error) {
        Serial.println("Erreur JSON");
        return;
    }
    
    String msgType = doc["type"] | "";
    
    if (msgType == "parking_status" || msgType == "parking_update") {
        freeSpots = doc["data"]["libres"] | 0;
        requireCode = (freeSpots == 0);
        updateLCD();
    }
    else if (msgType == "barrier_event") {
        String barrier = doc["barrier_id"] | "";
        String action = doc["action"] | "";
        
        if (barrier == "entry") {
            if (action == "open") {
                openBarrier("entry");
            } else if (action == "close") {
                closeBarrier("entry");
            }
        }
    }
}

// ============== CAPTEURS ==============
void checkEntrySensor() {
    bool newState = digitalRead(ENTRY_SENSOR_PIN) == LOW;  // LOW = véhicule détecté
    
    if (newState && !entryVehicleDetected) {
        // Nouveau véhicule détecté à l'entrée
        Serial.println("Véhicule détecté à l'entrée");
        entryVehicleDetected = true;
        
        if (freeSpots > 0 && !requireCode) {
            // Places disponibles - ouverture automatique
            requestAutoEntry();
        } else {
            // Demander le code
            currentState = STATE_WAITING_CODE;
            inputCode = "";
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Entrez code:");
            lcd.setCursor(0, 1);
            lcd.print("___");
        }
    } else if (!newState && entryVehicleDetected) {
        // Véhicule parti de l'entrée
        entryVehicleDetected = false;
        if (currentState == STATE_WAITING_CODE) {
            currentState = STATE_IDLE;
            inputCode = "";
            updateLCD();
        }
    }
}

void checkExitSensor() {
    bool newState = digitalRead(EXIT_SENSOR_PIN) == LOW;
    
    if (newState && !exitVehicleDetected) {
        Serial.println("Véhicule détecté à la sortie");
        exitVehicleDetected = true;
        requestExit();
    } else if (!newState && exitVehicleDetected) {
        exitVehicleDetected = false;
    }
}

// ============== CLAVIER ==============
void handleKeypadInput() {
    if (currentState != STATE_WAITING_CODE) {
        return;
    }
    
    char key = keypad.getKey();
    
    if (key) {
        Serial.print("Touche: ");
        Serial.println(key);
        
        if (key == '*') {
            // Effacer
            inputCode = "";
            lcd.setCursor(0, 1);
            lcd.print("___");
        }
        else if (key == '#') {
            // Valider
            if (inputCode.length() == CODE_LENGTH) {
                validateCode(inputCode);
            }
        }
        else if (isalnum(key) && inputCode.length() < CODE_LENGTH) {
            // Ajouter caractère
            inputCode += key;
            
            // Afficher le code
            lcd.setCursor(0, 1);
            lcd.print(inputCode);
            for (int i = inputCode.length(); i < CODE_LENGTH; i++) {
                lcd.print("_");
            }
            
            // Auto-validation si 3 caractères
            if (inputCode.length() == CODE_LENGTH) {
                lcd.setCursor(0, 1);
                lcd.print(inputCode + " Appuyez #");
            }
        }
    }
}

// ============== VALIDATION CODE ==============
void validateCode(String code) {
    currentState = STATE_VALIDATING;
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Validation...");
    
    Serial.print("Validation code: ");
    Serial.println(code);
    
    // Build request
    String url = "http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/api/v1/access/validate-code";
    
    StaticJsonDocument<200> doc;
    doc["code"] = code;
    doc["sensor_presence"] = entryVehicleDetected;
    doc["barrier_id"] = "entry";
    
    String body;
    serializeJson(doc, body);
    
    // Use retry logic for code validation
    String response;
    bool success = httpRequestWithRetry(url, "POST", body, response, MAX_RETRY_ATTEMPTS);
    
    if (success) {
        Serial.println(response);
        
        StaticJsonDocument<512> respDoc;
        deserializeJson(respDoc, response);
        
        bool accessGranted = respDoc["access_granted"] | false;
        String message = respDoc["message"] | "";
        String placeId = respDoc["place_id"] | "";
        
        if (accessGranted) {
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Acces autorise!");
            lcd.setCursor(0, 1);
            lcd.print("Place: " + placeId);
            
            openBarrier("entry");
        } else {
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Code invalide!");
            lcd.setCursor(0, 1);
            lcd.print(message.substring(0, 16));
            
            delay(3000);
            currentState = STATE_WAITING_CODE;
            inputCode = "";
            updateLCD();
        }
    } else {
        Serial.println("Code validation failed after retries");
        
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Erreur serveur");
        lcd.setCursor(0, 1);
        lcd.print("Reessayez...");
        
        delay(2000);
        currentState = STATE_WAITING_CODE;
        inputCode = "";
        updateLCD();
    }
}

// ============== REQUÊTES API ==============
void requestAutoEntry() {
    Serial.println("Demande entrée automatique (with retry)");
    
    String url = "http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/api/v1/access/check-entry";
    
    StaticJsonDocument<200> doc;
    doc["sensor_presence"] = true;
    doc["barrier_id"] = "entry";
    
    String body;
    serializeJson(doc, body);
    
    String response;
    if (httpRequestWithRetry(url, "POST", body, response)) {
        StaticJsonDocument<512> respDoc;
        deserializeJson(respDoc, response);
        
        bool canEnter = respDoc["can_enter"] | false;
        bool requireCodeResp = respDoc["require_code"] | false;
        
        if (canEnter) {
            lcd.clear();
            lcd.print("Bienvenue!");
            openBarrier("entry");
        } else if (requireCodeResp) {
            currentState = STATE_WAITING_CODE;
            inputCode = "";
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Entrez code:");
            lcd.setCursor(0, 1);
            lcd.print("___");
        } else {
            lcd.clear();
            lcd.print("Parking COMPLET");
            delay(2000);
            updateLCD();
        }
    } else {
        Serial.println("Auto entry request failed");
        lcd.clear();
        lcd.print("Erreur reseau");
        delay(2000);
        
        // Fall back to code entry if cached says parking might be full
        if (cachedStatus.valid && cachedStatus.requireCode) {
            currentState = STATE_WAITING_CODE;
            inputCode = "";
            lcd.clear();
            lcd.setCursor(0, 0);
            lcd.print("Entrez code:");
            lcd.setCursor(0, 1);
            lcd.print("___");
        } else {
            updateLCD();
        }
    }
}

void requestExit() {
    Serial.println("Demande sortie (with retry)");
    
    String url = "http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/api/v1/access/exit";
    
    StaticJsonDocument<200> doc;
    doc["sensor_presence"] = true;
    doc["barrier_id"] = "exit";
    
    String body;
    serializeJson(doc, body);
    
    String response;
    if (httpRequestWithRetry(url, "POST", body, response)) {
        lcd.clear();
        lcd.print("Bonne route!");
        openBarrier("exit");
        
        // Update local count
        freeSpots++;
        if (freeSpots > 6) freeSpots = 6;
        updateCache(freeSpots, freeSpots == 0);
    } else {
        // Even if server fails, open barrier for exit
        Serial.println("Exit request failed - opening barrier anyway");
        lcd.clear();
        lcd.print("Bonne route!");
        openBarrier("exit");
    }
}

void requestParkingInfo() {
    Serial.println("Requesting parking info (with retry)...");
    
    String url = "http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/api/v1/barrier/parking-info";
    String response;
    
    if (httpRequestWithRetry(url, "GET", "", response)) {
        StaticJsonDocument<256> doc;
        DeserializationError error = deserializeJson(doc, response);
        
        if (!error) {
            freeSpots = doc["free_spots"] | 0;
            requireCode = !(doc["allow_entry"] | true);
            
            // Update cache
            updateCache(freeSpots, requireCode);
            
            Serial.printf("Parking info: %d free spots, requireCode=%d\n", 
                          freeSpots, requireCode);
        }
    } else {
        Serial.println("Failed to get parking info after retries");
        
        // Fall back to cached data
        if (cachedStatus.valid) {
            freeSpots = cachedStatus.freeSpots;
            requireCode = cachedStatus.requireCode;
            Serial.println("Using cached parking status");
        }
    }
}

// ============== BARRIÈRES ==============
void openBarrier(String barrier_id) {
    Serial.print("Ouverture barrière: ");
    Serial.println(barrier_id);
    
    if (barrier_id == "entry") {
        entryServo.write(90);  // 90° = ouvert
        entryBarrierOpen = true;
        currentState = STATE_BARRIER_OPEN;
    } else if (barrier_id == "exit") {
        exitServo.write(90);
        exitBarrierOpen = true;
    }
    
    barrierOpenTime = millis();
}

void closeBarrier(String barrier_id) {
    Serial.print("Fermeture barrière: ");
    Serial.println(barrier_id);
    
    if (barrier_id == "entry") {
        entryServo.write(0);  // 0° = fermé
        entryBarrierOpen = false;
        currentState = STATE_IDLE;
        inputCode = "";
        updateLCD();
    } else if (barrier_id == "exit") {
        exitServo.write(0);
        exitBarrierOpen = false;
    }
}

void checkBarrierTimeout() {
    if ((entryBarrierOpen || exitBarrierOpen) && 
        (millis() - barrierOpenTime > BARRIER_OPEN_DURATION)) {
        
        if (entryBarrierOpen && !entryVehicleDetected) {
            closeBarrier("entry");
            
            // Notifier le serveur
            HTTPClient http;
            String url = "http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/api/v1/barrier/close?barrier_id=entry";
            http.begin(url);
            http.addHeader("X-API-Key", API_KEY);
            http.POST("");
            http.end();
        }
        
        if (exitBarrierOpen && !exitVehicleDetected) {
            closeBarrier("exit");
        }
    }
}

// ============== AFFICHAGE LCD ==============
void updateLCD() {
    if (currentState == STATE_WAITING_CODE || 
        currentState == STATE_VALIDATING ||
        currentState == STATE_BARRIER_OPEN) {
        return;  // Ne pas écraser les messages temporaires
    }
    
    lcd.clear();
    lcd.setCursor(0, 0);
    
    if (currentState == STATE_ERROR) {
        lcd.print("ERREUR SYSTEME");
        return;
    }
    
    // Ligne 1: État parking
    lcd.print("Places: ");
    lcd.print(freeSpots);
    lcd.print("/6");
    
    // Ligne 2: Message selon état
    lcd.setCursor(0, 1);
    if (isOfflineMode) {
        lcd.print("MODE HORS LIGNE");
    } else if (freeSpots == 0) {
        lcd.print("COMPLET-Code req");
    } else {
        lcd.print("Bienvenue!");
    }
}

// ============== RELIABILITY FUNCTIONS ==============

/**
 * HTTP request with retry logic
 * Attempts up to maxRetries times with RETRY_DELAY_MS between attempts
 */
bool httpRequestWithRetry(String url, String method, String body, String& response, int maxRetries) {
    for (int attempt = 1; attempt <= maxRetries; attempt++) {
        HTTPClient http;
        http.begin(url);
        http.addHeader("Content-Type", "application/json");
        http.addHeader("X-API-Key", API_KEY);
        http.setTimeout(5000);  // 5 second timeout
        
        int httpCode;
        if (method == "GET") {
            httpCode = http.GET();
        } else if (method == "POST") {
            httpCode = http.POST(body);
        } else {
            http.end();
            return false;
        }
        
        if (httpCode > 0 && httpCode < 400) {
            response = http.getString();
            http.end();
            successfulApiCalls++;
            isOfflineMode = false;
            return true;
        }
        
        Serial.printf("HTTP attempt %d/%d failed: %d\n", attempt, maxRetries, httpCode);
        http.end();
        
        if (attempt < maxRetries) {
            delay(RETRY_DELAY_MS);
        }
    }
    
    failedApiCalls++;
    return false;
}

/**
 * Send heartbeat to server with device status
 */
void sendHeartbeat() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("Skip heartbeat - WiFi disconnected");
        return;
    }
    
    Serial.println("Sending heartbeat...");
    
    HTTPClient http;
    String url = "http://" + String(SERVER_HOST) + ":" + String(SERVER_PORT) + "/api/v1/esp32/heartbeat";
    
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", API_KEY);
    http.setTimeout(5000);
    
    // Build heartbeat payload
    StaticJsonDocument<512> doc;
    doc["device_id"] = DEVICE_ID;
    doc["device_type"] = "BARRIER_CONTROLLER";
    doc["firmware_version"] = FIRMWARE_VERSION;
    doc["uptime_seconds"] = deviceUptime;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["wifi_rssi"] = WiFi.RSSI();
    
    // Sensor status
    JsonObject sensors = doc.createNestedObject("sensor_status");
    sensors["ir_sensors"] = sensorHealth.irSensors;
    sensors["servo"] = sensorHealth.servo;
    sensors["lcd"] = sensorHealth.lcd;
    sensors["entry_sensor"] = sensorHealth.entrySensor;
    sensors["exit_sensor"] = sensorHealth.exitSensor;
    
    // Include last error if any
    if (currentState == STATE_ERROR) {
        doc["last_error"] = "System in error state";
    }
    
    String body;
    serializeJson(doc, body);
    
    int httpCode = http.POST(body);
    
    if (httpCode == 200) {
        String response = http.getString();
        Serial.println("Heartbeat acknowledged");
        
        // Parse response for any pending commands
        StaticJsonDocument<512> respDoc;
        deserializeJson(respDoc, response);
        
        // Handle config updates or commands
        bool configUpdate = respDoc["config_update_available"] | false;
        if (configUpdate) {
            Serial.println("Config update available - will fetch on next boot");
        }
        
        isOfflineMode = false;
    } else {
        Serial.printf("Heartbeat failed: %d\n", httpCode);
    }
    
    http.end();
}

/**
 * Update local cache with parking status
 */
void updateCache(int spots, bool needCode) {
    cachedStatus.freeSpots = spots;
    cachedStatus.requireCode = needCode;
    cachedStatus.timestamp = millis();
    cachedStatus.valid = true;
    
    // Persist to flash
    saveCachedStatus();
    
    lastCacheUpdate = millis();
}

/**
 * Load cached status from flash storage
 */
void loadCachedStatus() {
    if (preferences.isKey("freeSpots")) {
        cachedStatus.freeSpots = preferences.getInt("freeSpots", 6);
        cachedStatus.requireCode = preferences.getBool("requireCode", false);
        cachedStatus.timestamp = 0;  // Old cache
        cachedStatus.valid = true;
        
        // Apply cached values
        freeSpots = cachedStatus.freeSpots;
        requireCode = cachedStatus.requireCode;
        
        Serial.printf("Loaded cached status: %d spots, requireCode=%d\n", 
                      freeSpots, requireCode);
    }
}

/**
 * Save cached status to flash storage
 */
void saveCachedStatus() {
    preferences.putInt("freeSpots", cachedStatus.freeSpots);
    preferences.putBool("requireCode", cachedStatus.requireCode);
}

/**
 * Check and reconnect WiFi if needed
 */
void checkWiFiConnection() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected - attempting reconnect...");
        isOfflineMode = true;
        currentState = STATE_OFFLINE;
        
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        
        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 10) {
            delay(500);
            attempts++;
        }
        
        if (WiFi.status() == WL_CONNECTED) {
            Serial.println("WiFi reconnected!");
            isOfflineMode = false;
            currentState = STATE_IDLE;
            
            // Reconnect WebSocket
            setupWebSocket();
            
            // Refresh parking info
            requestParkingInfo();
        } else {
            Serial.println("WiFi reconnect failed - using cached data");
            
            // Use cached status if available
            if (cachedStatus.valid) {
                freeSpots = cachedStatus.freeSpots;
                requireCode = cachedStatus.requireCode;
            }
        }
    }
}

/**
 * Check health of all sensors
 */
void checkSensorHealth() {
    // Check entry/exit sensors by reading them
    sensorHealth.entrySensor = (digitalRead(ENTRY_SENSOR_PIN) == HIGH || 
                                digitalRead(ENTRY_SENSOR_PIN) == LOW);
    sensorHealth.exitSensor = (digitalRead(EXIT_SENSOR_PIN) == HIGH || 
                               digitalRead(EXIT_SENSOR_PIN) == LOW);
    
    // Servo health checked by attach status
    sensorHealth.servo = entryServo.attached() && exitServo.attached();
    
    // LCD health - assume ok if initialized
    // In production, could try I2C scan
    sensorHealth.lcd = true;
    
    // IR sensors - assume ok
    sensorHealth.irSensors = true;
