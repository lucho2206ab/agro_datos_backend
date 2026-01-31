import os
import requests
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

# --- CONFIGURACIÓN ---
LAT = -33.0100
LON = -68.8667
PARCELA_ID = 1 
# Nueva API Key de OpenWeatherMap
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "1c32652573b1cc92d10e022f1c8a69b3")

def get_db_connection():
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT", "5432")
    # Aseguramos el uso de SSL para Supabase/Render
    uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
    return psycopg2.connect(uri)

def obtener_clima_openweather():
    """
    Obtiene clima actual desde OpenWeatherMap.
    Documentación: https://openweathermap.org/current
    """
    print(f"Solicitando clima a OpenWeatherMap...")
    
    # Parámetros: lat, lon, api_key y units=metric (Celsius)
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={OPENWEATHER_API_KEY}&units=metric"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            
            # 1. Temperatura (Celsius)
            temp = data.get('main', {}).get('temp', 0.0)
            
            # 2. Precipitación (mm en la última hora)
            # OpenWeather solo envía la clave 'rain' si hay lluvia registrada.
            rain_data = data.get('rain', {})
            lluvia_mm = rain_data.get('1h', 0.0)
            
            print(f"DEBUG: Datos obtenidos. Temp: {temp}°C, Lluvia (1h): {lluvia_mm}mm")
            return {"temp": temp, "lluvia": lluvia_mm}
        
        elif response.status_code == 401:
            print("❌ Error: API Key inválida o no activa aún.")
            return None
        else:
            print(f"❌ Error API OpenWeather: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None

def guardar_clima():
    clima = obtener_clima_openweather()
    if not clima:
        print("⚠️ No se pudo obtener datos del clima. Abortando guardado.")
        return

    # --- HORA LOCAL ARGENTINA ---
    try:
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora_ar = datetime.now(tz_ar)
        # Formateamos para que Postgres lo entienda correctamente sin problemas de offset
        fecha_final = ahora_ar.replace(tzinfo=None)
    except Exception as e:
        print(f"Error calculando zona horaria: {e}")
        fecha_final = datetime.now()

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
        INSERT INTO dato_clima (parcela_id, fecha_hora, temperatura_c, precipitacion_mm)
        VALUES (%s, %s, %s, %s);
        """
        cur.execute(sql, (PARCELA_ID, fecha_final, clima['temp'], clima['lluvia']))
        conn.commit()
        
        print(f"✅ REGISTRO EXITOSO: {fecha_final.strftime('%H:%M:%S')} | Temp: {clima['temp']}°C | Lluvia: {clima['lluvia']}mm")
        
    except Exception as e:
        print(f"❌ Error DB: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    guardar_clima()