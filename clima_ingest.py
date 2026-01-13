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
    Obtiene clima desde StormGlass con lógica de respaldo para precipitación.
    """
    print(f"Solicitando clima a StormGlass (Luján de Cuyo)...")
    
    params = "airTemperature,precipitation"
    url = f"https://api.stormglass.io/v2/weather/point?lat={LAT}&lng={LON}&params={params}"
    
    headers = {'Authorization': STORMGLASS_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if 'hours' not in data or len(data['hours']) == 0:
                print("⚠️ StormGlass no devolvió datos para esta hora.")
                return None
                
            current_data = data['hours'][0]
            
            # Lógica de extracción segura de diccionarios
            precip_dict = current_data.get('precipitation', {})
            # Intentamos obtener de cualquier fuente disponible (sg, noaa, dwd, etc)
            lluvia_mm = next(iter(precip_dict.values()), 0.0) if precip_dict else 0.0
            
            temp_dict = current_data.get('airTemperature', {})
            temp = next(iter(temp_dict.values()), 0.0) if temp_dict else 0.0
            
            print(f"DEBUG: Temp: {temp}, Lluvia: {lluvia_mm}")
            return {"temp": temp, "lluvia": lluvia_mm}
        else:
            print(f"❌ Error API StormGlass: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None

def guardar_clima():
    clima = obtener_clima_stormglass()
    if not clima:
        return

    # --- HORA LOCAL COMO TEXTO (NAIVE) ---
    try:
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora_ar = datetime.now(tz_ar)
        fecha_str = ahora_ar.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"Error calculando zona horaria: {e}")
        fecha_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
        INSERT INTO dato_clima (parcela_id, fecha_hora, temperatura_c, precipitacion_mm)
        VALUES (%s, %s, %s, %s);
        """
        cur.execute(sql, (PARCELA_ID, fecha_str, clima['temp'], clima['lluvia']))
        conn.commit()
        
        print(f"✅ REGISTRO EXITOSO: {fecha_str} | Lluvia: {clima['lluvia']}mm")
        
    except Exception as e:
        print(f"❌ Error DB: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    guardar_clima()