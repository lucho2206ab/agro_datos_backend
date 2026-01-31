#include <esp_now.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

// ===================================================
// 🔐 CREDENCIALES WIFI
// ===================================================
const char* ssid     = "MovistarFibra-758990";
const char* password = "Valen2012";

// ===================================================
// 🌐 CONFIGURACIÓN API
// ===================================================
const char* serverUrl   = "https://agro-datos-backend.onrender.com/api/lectura";
const char* apiKeyValue = "asic2025";

// ===================================================
// 📦 ESTRUCTURA ESP-NOW (DEBE COINCIDIR CON SATÉLITE)
// ===================================================
typedef struct struct_message {
    int id;
    int humedad;
} struct_message;

struct_message incomingReadings;

// ===================================================
// 📥 VARIABLES PARA PROCESAR FUERA DEL CALLBACK
// ===================================================
volatile bool hayLecturaPendiente = false;
int sensorPendiente  = 0;
int humedadPendiente = 0;

// ===================================================
// 📤 ENVÍO HTTPS AL SERVIDOR
// ===================================================
void enviarLectura(int idSensor, int valorHumedad) {

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[WIFI] No conectado, no se envía.");
        return;
    }

    WiFiClientSecure client;
    client.setInsecure();                 // Render usa TLS válido, pero evitamos problemas
    client.setHandshakeTimeout(15);       // Importante para Render

    HTTPClient http;
    http.setTimeout(40000);               // Render puede tardar

    if (!http.begin(client, serverUrl)) {
        Serial.println("[HTTP] No se pudo iniciar conexión");
        return;
    }

    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", apiKeyValue);

    // JSON exacto que espera tu backend
    StaticJsonDocument<256> doc;
    doc["sensor_id"]   = idSensor;
    doc["humedad"]     = valorHumedad;
    doc["temperatura"] = nullptr;   // genera literal null

    String payload;
    serializeJson(doc, payload);

    Serial.print("[DEBUG] Payload: ");
    Serial.println(payload);

    int httpCode = http.POST(payload);

    if (httpCode > 0) {
        Serial.printf("[HTTP] Código: %d\n", httpCode);
        Serial.println("[HTTP] Respuesta:");
        Serial.println(http.getString());
    } else {
        Serial.printf("[FALLO] Error: %s\n",
                      http.errorToString(httpCode).c_str());
    }

    http.end();
}

// ===================================================
// 📡 CALLBACK ESP-NOW (NO HACER HTTP ACÁ)
// ===================================================
void OnDataRecv(const esp_now_recv_info *info,
                const uint8_t *incomingData,
                int len) {

    memcpy(&incomingReadings, incomingData, sizeof(incomingReadings));

    sensorPendiente  = incomingReadings.id;
    humedadPendiente = incomingReadings.humedad;
    hayLecturaPendiente = true;

    Serial.printf(
        "\n[ESP-NOW] Nodo %d -> Humedad: %d\n",
        sensorPendiente,
        humedadPendiente
    );
}

// ===================================================
// ⚙️ SETUP
// ===================================================
void setup() {
    Serial.begin(115200);
    delay(1000);

    // ---- WIFI ----
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    WiFi.setSleep(false);   // MUY IMPORTANTE

    Serial.print("[WIFI] Conectando");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.println("\n[WIFI] Conectado");
    Serial.print("[WIFI] IP: ");
    Serial.println(WiFi.localIP());

    // ---- ESP-NOW ----
    if (esp_now_init() != ESP_OK) {
        Serial.println("[ESP-NOW] Error al iniciar");
        return;
    }

    esp_now_register_recv_cb(OnDataRecv);

    Serial.println("[ESP-NOW] Listo para recibir datos");
}

// ===================================================
// 🔁 LOOP
// ===================================================
void loop() {

    // Procesamos la lectura FUERA del callback
    if (hayLecturaPendiente) {
        hayLecturaPendiente = false;
        enviarLectura(sensorPendiente, humedadPendiente);
    }

    delay(10);
}
