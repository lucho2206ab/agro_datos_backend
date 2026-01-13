#include "FS.h"
#include "SD.h"
#include "SPI.h"

// --- CONFIGURACIÓN DE TIEMPOS ---
// Define cada cuánto tiempo despertar (en segundos)
// Ejemplo: 6 horas = 6 * 3600 = 21600 segundos
const uint64_t TIEMPO_DORMIR_SEG = 21600; 

// --- PINES ---
const int SD_CS = 5; 
const int SENSOR_PIN = 36; // Pin VP / A0
const int SENSOR_VCC = 12; // Pin para encender/apagar el sensor

// Variable persistente en la memoria RTC (no se borra durante el Deep Sleep)
RTC_DATA_ATTR int contadorMuestras = 0;

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_VCC, OUTPUT);
  
  // No iniciamos WiFi aquí, lo mantenemos apagado para ahorrar energía
  
  // 1. Inicializar SD
  if(!SD.begin(SD_CS)){
    Serial.println("Error: SD no detectada");
    return;
  }

  // 2. Leer Sensor (Encendido rápido)
  digitalWrite(SENSOR_VCC, HIGH); 
  delay(150); // Tiempo para que el sensor se estabilice
  int lecturaHumedad = analogRead(SENSOR_PIN);
  digitalWrite(SENSOR_VCC, LOW); 

  // Incrementamos el contador de muestras
  contadorMuestras++;

  // 3. Guardar en SD
  // Formato: Muestra_Numero, Valor_Humedad
  File file = SD.open("/muestras_campo.csv", FILE_APPEND);
  if(file){
    file.print(contadorMuestras);
    file.print(",");
    file.println(lecturaHumedad);
    file.close();
    
    Serial.print("Muestra registrada #");
    Serial.print(contadorMuestras);
    Serial.print(": ");
    Serial.println(lecturaHumedad);
  } else {
    Serial.println("Error al escribir en SD");
  }

  // 4. Dormir Profundo (Deep Sleep)
  // El ESP32 apagará casi todo, incluyendo el procesador
  Serial.println("Durmiendo...");
  
  // Convertimos segundos a microsegundos
  esp_sleep_enable_timer_wakeup(TIEMPO_DORMIR_SEG * 1000000ULL);
  esp_deep_sleep_start();
}

void loop() {
  // El código nunca llega aquí por el Deep Sleep
}