#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "FS.h"
#include "SD.h"
#include "SPI.h"
#include "time.h"

// --- CONFIGURACIÓN DE TIEMPOS ---
// 1 hora = 3600 segundos * 1.000.000 us
#define TIME_TO_SLEEP  3600000000 

const int PIN_POWER_SENSOR = 12; 
const int PIN_SENSOR_HUMEDAD = 36; 
const int SENSOR_ID = 1;
const int SD_CS = 5; 

// Credenciales actualizadas según tu sketch original
const char* ssid = "Primera Zona + DGI";
const char* password = "agualimpia";
const char* serverUrl = "https://agro-datos-backend.onrender.com/api/lectura";

// --- CONFIGURACIÓN NTP (Argentina UTC-3) ---
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = -10800; 
const int   daylightOffset_sec = 0;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n--- DESPERTANDO (Modo Robusto) ---");
  
  // 1. MEDIR (Prioridad inicial para ahorrar batería)
  pinMode(PIN_POWER_SENSOR, OUTPUT);
  digitalWrite(PIN_POWER_SENSOR, HIGH); 
  delay(1000); 
  
  long suma = 0;
  for(int i=0; i<10; i++) {
    suma += analogRead(PIN_SENSOR_HUMEDAD);
    delay(20);
  }
  int valorCrudo = suma / 10;
  
  // Mantenemos TUS valores de calibración: Seco (2349) y Agua (795)
  float humedad = map(valorCrudo, 2349, 795, 0, 100);
  humedad = constrain(humedad, 0, 100);
  digitalWrite(PIN_POWER_SENSOR, LOW); 
  
  Serial.printf("Lectura cruda: %d | Humedad: %.2f%%\n", valorCrudo, humedad);

  // 2. CONECTAR WIFI CON REINTENTOS AMPLIADOS
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int intentos = 0;
  // Aumentado a 80 intentos para dar margen en el campo (aprox 40 seg)
  while (WiFi.status() != WL_CONNECTED && intentos < 80) {
    delay(500);
    if (intentos % 10 == 0) Serial.print(" Buscando WiFi...");
    intentos++;
  }

  String timestamp = "0000-00-00 00:00:00";
  bool wifiOk = (WiFi.status() == WL_CONNECTED);

  if (wifiOk) {
    Serial.println("\n✅ WiFi OK!");
    
    // Sincronizar hora
    configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
    struct tm timeinfo;
    if(getLocalTime(&timeinfo)){
        char buf[25];
        strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &timeinfo);
        timestamp = String(buf);
        Serial.println("⏰ Hora: " + timestamp);
    }

    // Enviar datos
    bool enviado = enviarDatos(humedad);
    if(enviado) {
        guardarEnSD(humedad, timestamp, "ENVIADO_OK");
    } else {
        guardarEnSD(humedad, timestamp, "ERROR_HTTP");
    }
  } else {
    Serial.println("\n❌ Falla WiFi después de varios intentos.");
    guardarEnSD(humedad, timestamp, "SIN_WIFI");
  }

  // 3. DORMIR (Asegurando desconexión total para evitar cuelgues)
  Serial.println("Entrando en Deep Sleep...");
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  delay(100);
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP);
  esp_deep_sleep_start();
}

void loop() {}

void guardarEnSD(float valor, String hora, const char* estado) {
  if(SD.begin(SD_CS)) {
    char nombreArchivo[25];
    sprintf(nombreArchivo, "/sensor_%d.csv", SENSOR_ID);
    
    File file = SD.open(nombreArchivo, FILE_APPEND);
    if(file) {
      file.printf("%d,%s,%.2f,%s\n", SENSOR_ID, hora.c_str(), valor, estado);
      file.close();
      Serial.println("💾 Backup en SD OK.");
    } else {
      Serial.println("❌ Error al escribir en SD");
    }
    SD.end();
  } else {
    Serial.println("❌ SD no detectada");
  }
}

bool enviarDatos(float valorHumedad) {
  HTTPClient http;
  // Aumentamos el timeout a 25 seg para compensar latencia de red/servidor
  http.setTimeout(25000); 
  
  if (http.begin(serverUrl)) {
    http.addHeader("Content-Type", "application/json");
    
    StaticJsonDocument<200> doc;
    doc["sensor_id"] = SENSOR_ID;
    doc["humedad"] = valorHumedad;
    doc["temperatura"] = nullptr; 

    String jsonPayload;
    serializeJson(doc, jsonPayload);
    
    int httpResponseCode = http.POST(jsonPayload);
    Serial.printf("📡 Respuesta servidor: %d\n", httpResponseCode);
    
    // Lectura de respuesta para comando de reinicio remoto
    if (httpResponseCode >= 200 && httpResponseCode < 300) {
        String response = http.getString();
        if (response.indexOf("\"reset_device\":true") != -1) {
            Serial.println("⚠️ REINICIO REMOTO SOLICITADO POR EL SERVIDOR");
            http.end();
            delay(1000);
            ESP.restart(); 
        }
        http.end();
        return true;
    }
    
    http.end();
  }
  return false;
}