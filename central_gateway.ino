/*
  GATEWAY ESP32 - 
*/

#include <esp_now.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <esp_wifi.h>
#include <time.h>

// ════════════════════════════════════════════════════════════════════
// CONFIGURACIÓN
// ════════════════════════════════════════════════════════════════════

const char* ssid     = "MovistarFibra-758990";
const char* password = "Valen2012";

const char* serverUrl   = "https://agro-datos-backend.onrender.com/api/lectura";
const char* apiKeyValue = "asic2025";

// Servidor NTP para hora correcta
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = -3 * 3600;  // UTC-3 (Argentina)
const int daylightOffset_sec = 0;

// ════════════════════════════════════════════════════════════════════
// ESTRUCTURAS
// ════════════════════════════════════════════════════════════════════

typedef struct {
  int id;
  int humedad;
} struct_message;

typedef struct {
  int tipo;
} beacon_message;

struct_message incomingReadings;
beacon_message beacon = {999};

// ════════════════════════════════════════════════════════════════════
// VARIABLES GLOBALES
// ════════════════════════════════════════════════════════════════════

volatile bool hayLecturaPendiente = false;
int sensorPendiente;
int humedadPendiente;

unsigned long ultimoDato = 0;
unsigned long ultimoBeacon = 0;
unsigned long ultimoReporte = 0;

int canalWiFi = 6;

// ════════════════════════════════════════════════════════════════════
// CONECTAR WIFI
// ════════════════════════════════════════════════════════════════════

void conectarWiFi() {
  
  Serial.println("\n[WIFI] Iniciando conexión...");
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);
  
  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 30) {
    delay(500);
    Serial.print(".");
    intentos++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] ✅ Conectado");
    Serial.printf("[WIFI] IP: %s\n", WiFi.localIP().toString().c_str());
    
    canalWiFi = WiFi.channel();
    Serial.printf("[WIFI] Canal: %d\n", canalWiFi);
    
    // ✅ NUEVO: Sincronizar hora con servidor NTP
    Serial.println("[NTP] Sincronizando hora...");
    configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
    
    time_t now = time(nullptr);
    int intentosNTP = 0;
    while (localtime(&now)->tm_year < (2024 - 1900) && intentosNTP < 20) {
      delay(500);
      Serial.print(".");
      now = time(nullptr);
      intentosNTP++;
    }
    Serial.println();
    
    Serial.print("[NTP] ✅ Hora sincronizada: ");
    Serial.println(ctime(&now));
    
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(canalWiFi, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_promiscuous(false);
  } else {
    Serial.println("\n[WIFI] ❌ Fallo conexión (usando canal default)");
  }
}

// ════════════════════════════════════════════════════════════════════
// OBTENER HORA ACTUAL FORMATEADA
// ════════════════════════════════════════════════════════════════════

String obtenerHoraActual() {
  time_t ahora = time(nullptr);
  struct tm* timeinfo = localtime(&ahora);
  
  char buffer[30];
  strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", timeinfo);
  
  return String(buffer);
}

// ════════════════════════════════════════════════════════════════════
// ENVIAR A BACKEND - CON HORA DE RED
// ════════════════════════════════════════════════════════════════════

void enviarLectura(int idSensor, int valorHumedad) {
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WIFI] Reconectando...");
    conectarWiFi();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[HTTP] ❌ WiFi no disponible");
      return;
    }
  }
  
  WiFiClientSecure client;
  client.setInsecure();
  client.setHandshakeTimeout(15);
  
  HTTPClient http;
  http.setTimeout(30000);
  
  if (!http.begin(client, serverUrl)) {
    Serial.println("[HTTP] ❌ Error iniciar conexión");
    return;
  }
  
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKeyValue);
  
  StaticJsonDocument<256> doc;
  doc["sensor_id"]   = idSensor;
  doc["humedad"]     = valorHumedad;
  doc["fecha_hora"]  = obtenerHoraActual();
  
  String payload;
  serializeJson(doc, payload);
  
  Serial.printf("[HTTP] Enviando: Sensor %d, Humedad %d\n", idSensor, valorHumedad);
  Serial.printf("[HTTP] Hora: %s\n", obtenerHoraActual().c_str());
  Serial.printf("[DEBUG] Payload: %s\n", payload.c_str());
  
  int httpCode = http.POST(payload);
  
  if (httpCode > 0) {
    Serial.printf("[HTTP] ✅ Código: %d\n", httpCode);
    if (httpCode == 200 || httpCode == 201) {
      Serial.println("[HTTP] ✅ Lectura guardada en backend");
    } else {
      Serial.printf("[HTTP] ⚠️ Respuesta: %s\n", http.getString().c_str());
    }
  } else {
    Serial.printf("[HTTP] ❌ Error: %s\n", http.errorToString(httpCode).c_str());
  }
  
  http.end();
}

// ════════════════════════════════════════════════════════════════════
// CALLBACK ESP-NOW RX
// ════════════════════════════════════════════════════════════════════

void OnDataRecv(const esp_now_recv_info *info, const uint8_t *incomingData, int len) {
  
  if (len == sizeof(struct_message)) {
    memcpy(&incomingReadings, incomingData, sizeof(incomingReadings));
    
    sensorPendiente  = incomingReadings.id;
    humedadPendiente = incomingReadings.humedad;
    hayLecturaPendiente = true;
    
    ultimoDato = millis();
    
    Serial.printf("\n[ESP-NOW] 📡 Nodo %d recibido\n", sensorPendiente);
    Serial.printf("[ESP-NOW] Humedad: %d%%\n", humedadPendiente);
    Serial.printf("[ESP-NOW] MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                  info->src_addr[0], info->src_addr[1], info->src_addr[2],
                  info->src_addr[3], info->src_addr[4], info->src_addr[5]);
  }
}

// ════════════════════════════════════════════════════════════════════
// CALLBACK ESP-NOW TX
// ════════════════════════════════════════════════════════════════════

void OnDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
  if (status == ESP_NOW_SEND_SUCCESS) {
    Serial.println("[BEACON] ✅ TX OK");
  } else {
    Serial.println("[BEACON] ❌ TX Fallo");
  }
}

// ════════════════════════════════════════════════════════════════════
// ENVIAR BEACON
// ════════════════════════════════════════════════════════════════════

void enviarBeacon() {
  
  if (millis() - ultimoBeacon < 30000) return;
  
  ultimoBeacon = millis();
  
  uint8_t broadcast[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  
  if (esp_now_send(broadcast, (uint8_t*)&beacon, sizeof(beacon)) == ESP_OK) {
    Serial.println("[BEACON] 📢 Enviado");
  }
}

// ════════════════════════════════════════════════════════════════════
// REPORTE DE ESTADO
// ════════════════════════════════════════════════════════════════════

void reportarEstado() {
  
  if (millis() - ultimoReporte < 60000) return;
  
  ultimoReporte = millis();
  
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║         ESTADO DEL GATEWAY            ║");
  Serial.println("╠════════════════════════════════════════╣");
  Serial.printf("║ WiFi: %s\n", WiFi.status() == WL_CONNECTED ? "✅ Conectado" : "❌ Desconectado");
  Serial.printf("║ IP: %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("║ Canal: %d\n", canalWiFi);
  Serial.printf("║ Uptime: %lu segundos\n", millis() / 1000);
  Serial.println("╚════════════════════════════════════════╝");
}

// ════════════════════════════════════════════════════════════════════
// SETUP
// ════════════════════════════════════════════════════════════════════

void setup() {
  
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n╔════════════════════════════════════════════════════════════════╗");
  Serial.println("║         GATEWAY ESP32 - INICIALIZANDO                         ║");
  Serial.println("╚════════════════════════════════════════════════════════════════╝\n");
  
  conectarWiFi();
  
  if (esp_now_init() != ESP_OK) {
    Serial.println("[ESP-NOW] ❌ Error inicialización");
    while (1) delay(1000);
  }
  
  Serial.println("[ESP-NOW] ✅ Inicializado");
  
  esp_now_register_recv_cb(OnDataRecv);
  esp_now_register_send_cb(OnDataSent);
  
  Serial.println("\n[LISTO] Gateway esperando nodos...\n");
}

// ════════════════════════════════════════════════════════════════════
// LOOP
// ════════════════════════════════════════════════════════════════════

void loop() {
  
  if (hayLecturaPendiente) {
    hayLecturaPendiente = false;
    enviarLectura(sensorPendiente, humedadPendiente);
  }
  
  enviarBeacon();
  
  reportarEstado();
  
  delay(100);
}
