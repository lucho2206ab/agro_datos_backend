import os
import requests
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

# --- CONFIGURACIÓN ---
LAT = -33.035
LON = -68.877
PARCELA_ID = 1 
# Tu nueva API Key de StormGlass
STORMGLASS_API_KEY = "aabe22e4-ecf6-11f0-a0d3-0242ac130003-aabe2384-ecf6-11f0-a0d3-0242ac130003"

def get_db_connection():
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT", "5432")
    uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
    return psycopg2.connect(uri)

def obtener_clima_stormglass():
    """
    Obtiene clima actual desde StormGlass.io.
    """
    print(f"Solicitando clima a StormGlass (Luján de Cuyo)...")
    
    # StormGlass requiere definir qué parámetros queremos
    params = "airTemperature,precipitation"
    url = f"https://api.stormglass.io/v2/weather/point?lat={LAT}&lng={LON}&params={params}"
    
    headers = {
        'Authorization': STORMGLASS_API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            # StormGlass devuelve una lista de horas. Tomamos la primera (la más actual)
            current_data = data['hours'][0]
            
            # Los valores vienen en diccionarios por fuente (usualmente 'noaa' o 'sg')
            # Intentamos obtener el valor de la fuente 'sg' o el primero disponible
            temp = current_data.get('airTemperature', {}).get('noaa', 0.0)
            lluvia_mm = current_data.get('precipitation', {}).get('noaa', 0.0)
            
            print(f"DEBUG API StormGlass: Temp={temp}°C, Lluvia={lluvia_mm}mm")
            
            return {
                "temp": temp,
                "lluvia": lluvia_mm
            }
        else:
            print(f"Error StormGlass: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error de conexión con StormGlass: {e}")
        return None

def guardar_clima():
    clima = obtener_clima_stormglass()
    if not clima:
        print("❌ No se obtuvieron datos de StormGlass.")
        return

    # --- SOLUCIÓN HORA ARGENTINA DEFINITIVA ---
    # 1. Obtenemos la hora en la zona horaria de Argentina
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora_ar = datetime.now(tz_ar)
    
    # 2. IMPORTANTE: Eliminamos la información de zona horaria (hacerla 'naive')
    # Esto evita que la base de datos intente corregir o sumar horas según el servidor
    fecha_hora_final = ahora_ar.replace(tzinfo=None)

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
        INSERT INTO dato_clima (parcela_id, fecha_hora, temperatura_c, precipitacion_mm)
        VALUES (%s, %s, %s, %s);
        """
        cur.execute(sql, (PARCELA_ID, fecha_hora_final, clima['temp'], clima['lluvia']))
        conn.commit()
        print(f"✅ Guardado en DB: {clima['temp']}°C y {clima['lluvia']}mm")
        print(f"⏰ Hora registrada (AR): {fecha_hora_final.strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ Error DB: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    guardar_clima()