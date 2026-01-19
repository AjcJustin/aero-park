/**
 * AeroPark Smart System - ESP32 Parking Sensor Client
 * 
 * This code runs on ESP-32D microcontroller to detect vehicle presence
 * and report status to the AeroPark backend.
 * 
 * Hardware Setup:
 * - ESP-32D development board
 * - HC-SR04 Ultrasonic sensor (or similar)
 *   - TRIG pin -> GPIO 5
 *   - ECHO pin -> GPIO 18
 * - Optional: Status LED -> GPIO 2 (built-in LED on most boards)
 * 
 * Features:
 * - Connects to WiFi network
 * - Periodically measures distance using ultrasonic sensor
 * - Detects vehicle presence based on distance threshold
 * - Sends HTTP POST to backend when status changes
 * - Includes retry logic for failed requests
 * - Sends periodic heartbeat to backend
 * - LED indicators for status
 * 
 * Author: AeroPark Development Team
 * Version: 1.0.0
 * Date: 2024
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ==================== CONFIGURATION ====================
// WiFi credentials - UPDATE THESE
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Backend server configuration - UPDATE THESE
const char* SERVER_HOST = "YOUR_SERVER_IP_OR_DOMAIN";
const int SERVER_PORT = 8000;
const char* API_KEY = "YOUR_SENSOR_API_KEY_MIN_32_CHARS";

// Sensor identification
const char* SENSOR_ID = "ESP32-SENSOR-001";
const char* SPOT_ID = "YOUR_SPOT_ID";  // Get this from backend after spot creation

// Sensor pins (HC-SR04 Ultrasonic)
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;

// Status LED (built-in LED on most ESP32 boards)
const int LED_PIN = 2;

// Detection settings
const float DISTANCE_THRESHOLD_CM = 50.0;  // Object closer than this = occupied
const int MEASUREMENT_SAMPLES = 3;          // Number of readings to average
const unsigned long SAMPLE_DELAY_MS = 50;   // Delay between samples

// Timing settings
const unsigned long UPDATE_INTERVAL_MS = 5000;      // Check every 5 seconds
const unsigned long HEARTBEAT_INTERVAL_MS = 60000;  // Heartbeat every minute
const unsigned long WIFI_RETRY_DELAY_MS = 5000;     // WiFi reconnect delay
const int MAX_HTTP_RETRIES = 3;                     // Max retry attempts

// ==================== GLOBAL VARIABLES ====================
bool isOccupied = false;
bool lastReportedStatus = false;
unsigned long lastUpdateTime = 0;
unsigned long lastHeartbeatTime = 0;
bool wifiConnected = false;

// ==================== FUNCTION DECLARATIONS ====================
void setupWiFi();
void checkWiFiConnection();
float measureDistance();
bool detectVehicle();
void sendStatusUpdate(bool occupied);
void sendHeartbeat();
bool sendHttpPost(const char* endpoint, const String& payload);
void blinkLED(int times, int delayMs);
void setLED(bool on);

// ==================== SETUP ====================
void setup() {
    // Initialize serial communication
    Serial.begin(115200);
    delay(1000);
    
    Serial.println();
    Serial.println("=========================================");
    Serial.println("   AeroPark Smart System - ESP32 Sensor");
    Serial.println("=========================================");
    Serial.println();
    
    // Initialize pins
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(LED_PIN, OUTPUT);
    
    // Initial LED state
    setLED(false);
    
    // Print configuration
    Serial.println("Configuration:");
    Serial.print("  Sensor ID: ");
    Serial.println(SENSOR_ID);
    Serial.print("  Spot ID: ");
    Serial.println(SPOT_ID);
    Serial.print("  Server: ");
    Serial.print(SERVER_HOST);
    Serial.print(":");
    Serial.println(SERVER_PORT);
    Serial.print("  Distance Threshold: ");
    Serial.print(DISTANCE_THRESHOLD_CM);
    Serial.println(" cm");
    Serial.println();
    
    // Connect to WiFi
    setupWiFi();
    
    // Initial status check
    isOccupied = detectVehicle();
    lastReportedStatus = isOccupied;
    
    Serial.print("Initial status: ");
    Serial.println(isOccupied ? "OCCUPIED" : "FREE");
    
    // Send initial status
    sendStatusUpdate(isOccupied);
    
    // Indicate ready
    blinkLED(3, 200);
    
    Serial.println();
    Serial.println("Sensor ready and monitoring...");
    Serial.println();
}

// ==================== MAIN LOOP ====================
void loop() {
    // Check WiFi connection
    checkWiFiConnection();
    
    unsigned long currentTime = millis();
    
    // Check for status updates
    if (currentTime - lastUpdateTime >= UPDATE_INTERVAL_MS) {
        lastUpdateTime = currentTime;
        
        // Detect current vehicle presence
        isOccupied = detectVehicle();
        
        // Update LED to reflect current status
        setLED(isOccupied);
        
        // Only send update if status changed
        if (isOccupied != lastReportedStatus) {
            Serial.print("Status changed: ");
            Serial.print(lastReportedStatus ? "OCCUPIED" : "FREE");
            Serial.print(" -> ");
            Serial.println(isOccupied ? "OCCUPIED" : "FREE");
            
            sendStatusUpdate(isOccupied);
            lastReportedStatus = isOccupied;
        }
    }
    
    // Send periodic heartbeat
    if (currentTime - lastHeartbeatTime >= HEARTBEAT_INTERVAL_MS) {
        lastHeartbeatTime = currentTime;
        sendHeartbeat();
    }
    
    // Small delay to prevent tight loop
    delay(100);
}

// ==================== WIFI FUNCTIONS ====================

/**
 * Initialize WiFi connection
 */
void setupWiFi() {
    Serial.print("Connecting to WiFi: ");
    Serial.println(WIFI_SSID);
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
        
        // Blink LED while connecting
        setLED(attempts % 2 == 0);
    }
    
    Serial.println();
    
    if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        Serial.println("WiFi connected!");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
        Serial.print("Signal Strength (RSSI): ");
        Serial.print(WiFi.RSSI());
        Serial.println(" dBm");
    } else {
        wifiConnected = false;
        Serial.println("WiFi connection failed!");
        Serial.println("Will retry in background...");
    }
    
    setLED(false);
}

/**
 * Check and maintain WiFi connection
 */
void checkWiFiConnection() {
    if (WiFi.status() != WL_CONNECTED) {
        if (wifiConnected) {
            Serial.println("WiFi connection lost! Reconnecting...");
            wifiConnected = false;
        }
        
        WiFi.disconnect();
        delay(1000);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        
        // Wait for connection with timeout
        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 10) {
            delay(500);
            attempts++;
        }
        
        if (WiFi.status() == WL_CONNECTED) {
            wifiConnected = true;
            Serial.println("WiFi reconnected!");
            Serial.print("IP: ");
            Serial.println(WiFi.localIP());
        }
    }
}

// ==================== SENSOR FUNCTIONS ====================

/**
 * Measure distance using ultrasonic sensor
 * Returns average of multiple samples for reliability
 */
float measureDistance() {
    float totalDistance = 0;
    int validSamples = 0;
    
    for (int i = 0; i < MEASUREMENT_SAMPLES; i++) {
        // Clear trigger pin
        digitalWrite(TRIG_PIN, LOW);
        delayMicroseconds(2);
        
        // Send ultrasonic pulse
        digitalWrite(TRIG_PIN, HIGH);
        delayMicroseconds(10);
        digitalWrite(TRIG_PIN, LOW);
        
        // Measure echo duration
        long duration = pulseIn(ECHO_PIN, HIGH, 30000);  // 30ms timeout
        
        if (duration > 0) {
            // Calculate distance in cm
            // Speed of sound = 343 m/s = 0.0343 cm/µs
            // Distance = (duration * 0.0343) / 2
            float distance = (duration * 0.0343) / 2.0;
            
            // Filter out unrealistic readings
            if (distance > 0 && distance < 400) {
                totalDistance += distance;
                validSamples++;
            }
        }
        
        delay(SAMPLE_DELAY_MS);
    }
    
    if (validSamples > 0) {
        return totalDistance / validSamples;
    }
    
    // Return max distance if no valid readings
    return 400.0;
}

/**
 * Detect if a vehicle is present
 * Returns true if object detected within threshold
 */
bool detectVehicle() {
    float distance = measureDistance();
    
    Serial.print("Distance: ");
    Serial.print(distance, 1);
    Serial.print(" cm -> ");
    
    bool detected = distance < DISTANCE_THRESHOLD_CM;
    Serial.println(detected ? "VEHICLE DETECTED" : "NO VEHICLE");
    
    return detected;
}

// ==================== HTTP FUNCTIONS ====================

/**
 * Send status update to backend
 */
void sendStatusUpdate(bool occupied) {
    if (!wifiConnected) {
        Serial.println("Cannot send update - WiFi not connected");
        return;
    }
    
    // Create JSON payload
    StaticJsonDocument<256> doc;
    doc["spot_id"] = SPOT_ID;
    doc["status"] = occupied ? "occupied" : "free";
    doc["sensor_id"] = SENSOR_ID;
    doc["distance_cm"] = measureDistance();
    
    String payload;
    serializeJson(doc, payload);
    
    Serial.print("Sending status update: ");
    Serial.println(payload);
    
    bool success = sendHttpPost("/sensor/update", payload);
    
    if (success) {
        Serial.println("Status update sent successfully!");
        blinkLED(1, 100);
    } else {
        Serial.println("Failed to send status update!");
        blinkLED(5, 50);
    }
}

/**
 * Send heartbeat to backend
 */
void sendHeartbeat() {
    if (!wifiConnected) {
        return;
    }
    
    String url = "http://";
    url += SERVER_HOST;
    url += ":";
    url += SERVER_PORT;
    url += "/sensor/heartbeat?sensor_id=";
    url += SENSOR_ID;
    
    HTTPClient http;
    http.begin(url);
    http.addHeader("X-API-Key", API_KEY);
    http.addHeader("X-Sensor-ID", SENSOR_ID);
    
    int httpCode = http.POST("");
    
    if (httpCode == 200) {
        Serial.println("Heartbeat sent");
    } else {
        Serial.print("Heartbeat failed: ");
        Serial.println(httpCode);
    }
    
    http.end();
}

/**
 * Send HTTP POST request to backend
 * Includes retry logic for reliability
 */
bool sendHttpPost(const char* endpoint, const String& payload) {
    String url = "http://";
    url += SERVER_HOST;
    url += ":";
    url += SERVER_PORT;
    url += endpoint;
    
    for (int attempt = 1; attempt <= MAX_HTTP_RETRIES; attempt++) {
        Serial.print("HTTP POST attempt ");
        Serial.print(attempt);
        Serial.print("/");
        Serial.print(MAX_HTTP_RETRIES);
        Serial.print(" to ");
        Serial.println(url);
        
        HTTPClient http;
        http.begin(url);
        http.addHeader("Content-Type", "application/json");
        http.addHeader("X-API-Key", API_KEY);
        http.addHeader("X-Sensor-ID", SENSOR_ID);
        http.setTimeout(10000);  // 10 second timeout
        
        int httpCode = http.POST(payload);
        
        if (httpCode > 0) {
            Serial.print("HTTP Response: ");
            Serial.println(httpCode);
            
            if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED) {
                String response = http.getString();
                Serial.print("Response: ");
                Serial.println(response);
                http.end();
                return true;
            }
            
            // Log error response
            if (httpCode >= 400) {
                String response = http.getString();
                Serial.print("Error response: ");
                Serial.println(response);
            }
        } else {
            Serial.print("HTTP error: ");
            Serial.println(http.errorToString(httpCode));
        }
        
        http.end();
        
        // Wait before retry
        if (attempt < MAX_HTTP_RETRIES) {
            Serial.println("Retrying...");
            delay(1000 * attempt);  // Exponential backoff
        }
    }
    
    return false;
}

// ==================== LED FUNCTIONS ====================

/**
 * Blink LED multiple times
 */
void blinkLED(int times, int delayMs) {
    for (int i = 0; i < times; i++) {
        setLED(true);
        delay(delayMs);
        setLED(false);
        delay(delayMs);
    }
}

/**
 * Set LED state
 */
void setLED(bool on) {
    digitalWrite(LED_PIN, on ? HIGH : LOW);
}
