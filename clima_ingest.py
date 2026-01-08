import os
import requests
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

# --- CONFIGURACIÓN ---
# Coordenadas de Luján de Cuyo
LAT = -33.035
LON = -68.877
PARCELA_ID = 1 

def get_db_connection():
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT", "5432")
    uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
    return psycopg2.connect(uri)

def obtener_clima_open_meteo():
    """
    Obtiene clima actual desde Open-Meteo (Sin necesidad de API Key).
    """
    print(f"Solicitando clima a Open-Meteo para Luján de Cuyo...")
    # Solicitamos temperatura actual y precipitación de la última hora
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,precipitation,relative_humidity_2m&timezone=America%2FArgentina%2FBuenos_Aires"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            current = data.get('current', {})
            
            temp = current.get('temperature_2m')
            lluvia_mm = current.get('precipitation', 0.0)
            humedad = current.get('relative_humidity_2m')
            
            print(f"--- Datos Obtenidos ---")
            print(f"Temperatura: {temp}°C")
            print(f"Lluvia detectada: {lluvia_mm}mm")
            print(f"Humedad aire: {humedad}%")
            
            return {
                "temp": temp,
                "lluvia": lluvia_mm,
                "humedad": humedad
            }
        else:
            print(f"Error Open-Meteo: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error de conexión: {e}")
        return None

def guardar_clima():
    clima = obtener_clima_open_meteo()
    if not clima or clima['temp'] is None:
        print("❌ No se pudieron obtener datos válidos.")
        return

    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora = datetime.now(tz_ar)

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insertamos en dato_clima
        # Asegúrate de que las columnas coincidan con tu tabla
        sql = """
        INSERT INTO dato_clima (parcela_id, fecha_hora, temperatura_c, precipitacion_mm)
        VALUES (%s, %s, %s, %s);
        """
        cur.execute(sql, (PARCELA_ID, ahora, clima['temp'], clima['lluvia']))
        conn.commit()
        print(f"✅ Guardado en DB: {clima['lluvia']}mm de lluvia a las {ahora.strftime('%H:%M')}")
        
    except Exception as e:
        print(f"❌ Error DB: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    guardar_clima()