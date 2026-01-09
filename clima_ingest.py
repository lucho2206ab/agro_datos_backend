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
    Obtiene clima actual desde Open-Meteo.
    """
    print(f"Solicitando clima a Open-Meteo (Luján de Cuyo)...")
    # Usamos la API 'current' con temperatura y precipitación
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=temperature_2m,precipitation,relative_humidity_2m&timezone=America%2FArgentina%2FBuenos_Aires"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            current = data.get('current', {})
            
            temp = current.get('temperature_2m')
            # Open-Meteo devuelve la precipitación en mm
            lluvia_mm = current.get('precipitation', 0.0)
            
            print(f"DEBUG API: Temp={temp}, Lluvia={lluvia_mm}mm")
            
            return {
                "temp": temp,
                "lluvia": lluvia_mm
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
        print("❌ No se obtuvieron datos válidos.")
        return

    # --- SOLUCIÓN HORA ARGENTINA (Igual que app.py) ---
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora_ar = datetime.now(tz_ar)
    # Convertimos a 'naive' (sin zona horaria) para que la DB guarde literal
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
        print(f"✅ Guardado: {clima['temp']}°C y {clima['lluvia']}mm a las {fecha_hora_final.strftime('%H:%M:%S')}")
        
    except Exception as e:
        print(f"❌ Error DB: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    guardar_clima()