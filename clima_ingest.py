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
STORMGLASS_API_KEY = os.getenv("STORMGLASS_API_KEY", "aabe22e4-ecf6-11f0-a0d3-0242ac130003-aabe2384-ecf6-11f0-a0d3-0242ac130003")

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
    Obtiene clima desde StormGlass priorizando el modelo 'sg'.
    """
    print(f"Solicitando clima a StormGlass (Modelo SG)...")
    
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
            
            # --- EXTRACCIÓN CON PRIORIDAD EN 'sg' ---
            
            # 1. Temperatura
            temp_dict = current_data.get('airTemperature', {})
            # Intentamos obtener 'sg', si no existe, tomamos el primero disponible
            temp = temp_dict.get('sg', next(iter(temp_dict.values()), 0.0))
            
            # 2. Precipitación
            precip_dict = current_data.get('precipitation', {})
            # Intentamos obtener 'sg', si no existe, tomamos el primero disponible
            lluvia_mm = precip_dict.get('sg', next(iter(precip_dict.values()), 0.0))
            
            print(f"DEBUG: Fuente SG detectada. Temp: {temp}, Lluvia: {lluvia_mm}")
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

    # --- HORA LOCAL ARGENTINA ---
    try:
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora_ar = datetime.now(tz_ar)
        # Convertimos a naive para la base de datos
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