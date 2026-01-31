#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>

// MAC DE TU CENTRAL (IMPORTANTE)
uint8_t broadcastAddress[] = {0xB0, 0xA7, 0x32, 0xDB, 0x0E, 0x64}; 

// Parámetros de tiempo (8 horas) y Hardware
#define TIME_TO_SLEEP (8ULL * 60ULL * 60ULL * 1000000ULL) 
const int PIN_POWER_SENSOR = 12; 
const int PIN_SENSOR_HUMEDAD = 36; 
const int SENSOR_ID = 1; 
const int WIFI_CHANNEL = 6; // Debe coincidir con el de la Central

typedef struct struct_message {
    int id;
    int humedad;
} struct_message;

struct_message lectura;
esp_now_peer_info_t peerInfo;

// CORRECCIÓN DE LA FIRMA: Cambiamos uint8_t* por wifi_tx_info_t*
void OnDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
    Serial.print("\r\n>>> Estado del último envío: ");
    Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Éxito" : "Fallo");
}

void setup() {
    Serial.begin(115200);
    delay(100);

    // 1. GESTIÓN DE ENERGÍA Y LECTURA
    pinMode(PIN_POWER_SENSOR, OUTPUT);
    digitalWrite(PIN_POWER_SENSOR, HIGH);
    delay(500); // Tiempo de calentamiento del sensor

    long suma = 0;
    for(int i=0; i<15; i++) { 
        suma += analogRead(PIN_SENSOR_HUMEDAD); 
        delay(10); 
    }
    int valorADC = suma / 15;
    digitalWrite(PIN_POWER_SENSOR, LOW); // Apagamos para ahorrar energía

    // 2. CALIBRACIÓN (Tus parámetros específicos)
    // Seco: 2349, Mojado: 795
    lectura.humedad = constrain(map(valorADC, 2349, 795, 0, 100), 0, 100);
    lectura.id = SENSOR_ID;
    
    Serial.printf(">>> LECTURA ADC: %d | HUMEDAD: %d%%\n", valorADC, lectura.humedad);

    // 3. COMUNICACIÓN WIFI / ESP-NOW
    WiFi.mode(WIFI_STA);
    
    // Forzamos el canal antes de iniciar
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_promiscuous(false);

    if (esp_now_init() != ESP_OK) {
        Serial.println("Error inicializando ESP-NOW");
        esp_deep_sleep_start();
    }

    // Registramos el callback con el cast (esp_now_send_cb_t)
    esp_now_register_send_cb((esp_now_send_cb_t)OnDataSent);
    
    // Registrar el compañero (Central)
    memcpy(peerInfo.peer_addr, broadcastAddress, 6);
    peerInfo.channel = WIFI_CHANNEL;  
    peerInfo.encrypt = false;
    
    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("Error al añadir Peer");
        esp_deep_sleep_start();
    }

    // 4. ENVÍO DE DATOS
    Serial.println("Enviando datos...");
    esp_now_send(broadcastAddress, (uint8_t *) &lectura, sizeof(lectura));
    
    // Esperamos un segundo para asegurar que la radio termine el proceso
    delay(1000); 

    // 5. DEEP SLEEP
    Serial.println("Entrando en Deep Sleep (8 horas)...");
    esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP);
    esp_deep_sleep_start();
}

void loop() {
    // Nunca llega aquí
}