/*
  ╔════════════════════════════════════════════════════════════════════╗
  ║         NODO ESP32                                                 ║
  ╚════════════════════════════════════════════════════════════════════╝
*/

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <SPI.h>
#include <SD.h>

// ═══════════════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════════════

uint8_t gatewayMAC[] = {0xB0, 0xA7, 0x32, 0xDB, 0x0E, 0x64};

#define TIME_TO_SLEEP (2ULL * 60ULL * 60ULL * 1000000ULL)
#define MAX_REINTENTOS 3

#define PIN_POWER_SENSOR 12
#define PIN_SENSOR_HUMEDAD 36
#define SENSOR_ID 3

#define SD_CS_PIN 5
#define ARCHIVO_SD "/BUFFER.CSV"

const char* ssid = "MovistarFibra-758990";

// ═══════════════════════════════════════════════════════════════════
// STRUCT
// ═══════════════════════════════════════════════════════════════════

typedef struct {
  int id;
  int humedad;
} struct_message;

struct_message lectura;
esp_now_peer_info_t peerInfo;

volatile bool envioOK = false;

// ═══════════════════════════════════════════════════════════════════
// CALLBACK
// ═══════════════════════════════════════════════════════════════════

void OnDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
  envioOK = (status == ESP_NOW_SEND_SUCCESS);
}

// ═══════════════════════════════════════════════════════════════════
// DETECTAR CANAL
// ═══════════════════════════════════════════════════════════════════

int detectarCanal() {

  Serial.println("🔎 Buscando canal...");

  WiFi.disconnect();
  delay(200);

  int n = WiFi.scanNetworks();

  for(int i = 0; i < n; i++){
    if(WiFi.SSID(i) == ssid){
      int canal = WiFi.channel(i);
      Serial.printf("✅ Canal %d\n", canal);
      return canal;
    }
  }

  Serial.println("⚠️ Fallback canal 1");
  return 1;
}

// ═══════════════════════════════════════════════════════════════════
// SD BACKUP
// ═══════════════════════════════════════════════════════════════════

void guardarEnSD(int id, int humedad){

  if(!SD.begin(SD_CS_PIN)) return;

  File f = SD.open(ARCHIVO_SD, FILE_APPEND);
  if(!f) return;

  f.printf("%d,%d,ERROR_ENVIO\n", id, humedad);
  f.close();

  Serial.println("📦 Backup SD");
}

// ═══════════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════════

void setup(){

  Serial.begin(115200);
  delay(500);

  bool errorEnvio = false;

  // ═══ SENSOR ═══

  pinMode(PIN_POWER_SENSOR, OUTPUT);
  digitalWrite(PIN_POWER_SENSOR, HIGH);
  delay(300);

  long suma = 0;
  for(int i = 0; i < 10; i++){
    suma += analogRead(PIN_SENSOR_HUMEDAD);
    delay(5);
  }

  digitalWrite(PIN_POWER_SENSOR, LOW);

  int valorADC = suma / 10;

  lectura.id = SENSOR_ID;
  lectura.humedad = constrain(map(valorADC, 2349, 795, 0, 100), 0, 100);

  Serial.printf("Nodo %d | HUM %d\n", SENSOR_ID, lectura.humedad);

  // ═══ WIFI ═══

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  delay(300);

  int canal = detectarCanal();

  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(canal, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  delay(200);

  // ═══ ESP NOW ═══

  if(esp_now_init() != ESP_OK){
    errorEnvio = true;
  }else{

    esp_now_register_send_cb(OnDataSent);

    memset(&peerInfo, 0, sizeof(peerInfo));
    memcpy(peerInfo.peer_addr, gatewayMAC, 6);
    peerInfo.channel = canal;
    peerInfo.encrypt = false;

    if(esp_now_add_peer(&peerInfo) != ESP_OK){
      errorEnvio = true;
    }else{

      bool enviado = false;

      for(int i = 0; i < MAX_REINTENTOS; i++){

        envioOK = false;

        Serial.printf("Intento %d\n", i+1);

        esp_now_send(gatewayMAC, (uint8_t*)&lectura, sizeof(lectura));

        unsigned long t0 = millis();

        while(!envioOK && millis()-t0 < 2000){
          delay(10);
        }

        if(envioOK){
          Serial.println("✅ ENVIO OK");
          enviado = true;
          break;
        }
      }

      if(!enviado) errorEnvio = true;
    }
  }

  if(errorEnvio){
    Serial.println("❌ Error envio");
    guardarEnSD(lectura.id, lectura.humedad);
  }

  // ═══ APAGADO TOTAL ═══

  esp_now_deinit();

  WiFi.disconnect(true, true);
  WiFi.mode(WIFI_OFF);
  btStop();

  esp_wifi_stop();

  delay(200);

  Serial.println("😴 Deep sleep");

  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP);
  esp_deep_sleep_start();
}

void loop(){}