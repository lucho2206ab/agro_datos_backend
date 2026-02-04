import os
import requests
import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import pytz
import json

load_dotenv()

# --- CONFIGURACIÓN ---
# ID de estación Perdriel (Luján de Cuyo) - La más cercana a tu zona
ESTACION_ID = 12
PARCELA_ID = 1

# API del Gobierno de Mendoza
API_URL = "https://agrometeo.mendoza.gov.ar/api/getUltimasInstantaneas.php"

def get_db_connection():
    """Conecta a Supabase/PostgreSQL"""
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT", "5432")
    
    uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
    return psycopg2.connect(uri)

def obtener_clima_gobierno():
    """
    Obtiene clima actual desde API oficial del Gobierno de Mendoza.
    Mucho más preciso para precipitación que OpenWeatherMap.
    
    Documentación: https://agrometeo.mendoza.gov.ar/
    API: https://agrometeo.mendoza.gov.ar/api/getUltimasInstantaneas.php?estacion=ID
    """
    print(f"[{datetime.now()}] Solicitando clima a API Gobierno Mendoza (Estación {ESTACION_ID})...")
    
    try:
        # Consultar la API con parámetro de estación
        params = {"estacion": ESTACION_ID}
        response = requests.get(API_URL, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # La API devuelve un array de registros o un objeto único
            # Si es array, tomamos el primero (más reciente)
            if isinstance(data, list) and len(data) > 0:
                registro = data[0]
            elif isinstance(data, dict):
                registro = data
            else:
                print("❌ Formato de respuesta no esperado")
                return None
            
            # Extraer datos del registro
            # Estos son los campos reales que devuelve la API
            temperatura = float(registro.get("tempAire", 0.0))
            humedad = float(registro.get("humedad", 0.0))
            precipitacion = float(registro.get("precipitacion", 0.0))
            
            # Debug: mostrar datos recibidos
            print(f"✓ Datos obtenidos:")
            print(f"  - Temperatura: {temperatura}°C")
            print(f"  - Humedad: {humedad}%")
            print(f"  - Precipitación: {precipitacion}mm")
            
            return {
                "temp": temperatura,
                "humedad": humedad,
                "lluvia": precipitacion
            }
        
        elif response.status_code == 404:
            print(f"❌ Error 404: Estación {ESTACION_ID} no encontrada")
            return None
        else:
            print(f"❌ Error API: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ Error: Timeout en la solicitud a la API")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar a la API")
        return None
    except json.JSONDecodeError:
        print("❌ Error: Respuesta JSON inválida")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

def guardar_clima():
    """Obtiene el clima y lo guarda en la BD"""
    clima = obtener_clima_gobierno()
    
    if not clima:
        print("⚠️ No se pudo obtener datos del clima. Abortando guardado.")
        return False

    # --- HORA LOCAL ARGENTINA ---
    try:
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora_ar = datetime.now(tz_ar)
        # Formateamos para que Postgres lo entienda correctamente
        fecha_final = ahora_ar.replace(tzinfo=None)
    except Exception as e:
        print(f"⚠️ Error calculando zona horaria: {e}")
        fecha_final = datetime.now()

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # INSERT con los campos que ya tienes en tu tabla
        # Si tu tabla no tiene humedad_ambiente, comenta esa línea
        sql = """
        INSERT INTO dato_clima (parcela_id, fecha_hora, temperatura_c, precipitacion_mm, humedad_ambiente)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        cur.execute(sql, (
            PARCELA_ID,
            fecha_final,
            clima['temp'],
            clima['lluvia'],
            clima['humedad']
        ))
        conn.commit()
        
        print(f"✅ REGISTRO EXITOSO:")
        print(f"   Fecha: {fecha_final.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Temperatura: {clima['temp']}°C")
        print(f"   Humedad: {clima['humedad']}%")
        print(f"   Precipitación: {clima['lluvia']}mm")
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Error BD: {e}")
        if conn: 
            conn.rollback()
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False
    finally:
        if conn: 
            conn.close()

if __name__ == "__main__":
    success = guardar_clima()
    exit(0 if success else 1)