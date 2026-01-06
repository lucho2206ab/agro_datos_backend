import os
import psycopg2
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno (Localmente desde .env, en GitHub desde Secrets)
load_dotenv()

# API gratuita que no requiere Key para uso básico
BASE_URL = "https://api.open-meteo.com/v1/forecast"

def get_db_connection():
    """Establece conexión con Supabase usando variables de entorno."""
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT")

    connection_uri = (
        f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        "?sslmode=require"
    )
    return psycopg2.connect(connection_uri)

def obtener_coordenadas_parcelas(conn):
    """Obtiene el ID y el centro geográfico de cada parcela usando PostGIS."""
    with conn.cursor() as cur:
        sql = """
            SELECT 
                p.id_parcela,
                p.nombre_parcela,
                ST_Y(ST_Centroid(gp.geometria_poligono)) as latitud,
                ST_X(ST_Centroid(gp.geometria_poligono)) as longitud
            FROM parcelas p
            JOIN geolocalizacion_parcelas gp ON p.id_parcela = gp.parcela_id;
        """
        try:
            cur.execute(sql)
            return cur.fetchall()
        except Exception as e:
            print(f"❌ Error consultando coordenadas: {e}")
            return []

def consultar_clima(lat, lon):
    """Llama a la API de Open-Meteo para obtener temperatura y lluvia."""
    params = {
        'latitude': lat,
        'longitude': lon,
        'current_weather': 'true',
        'timezone': 'auto'
    }
    try:
        r = requests.get(BASE_URL, params=params)
        r.raise_for_status()
        data = r.json()
        return {
            'temp': data['current_weather']['temperature'],
            'lluvia': data.get('current_weather', {}).get('precipitation', 0.0)
        }
    except Exception as e:
        print(f"⚠️ Error en API de Clima: {e}")
        return None

def guardar_datos(conn, parcela_id, clima):
    """Inserta la lectura de clima en la base de datos."""
    sql = """
        INSERT INTO dato_clima (parcela_id, fecha_hora, temperatura_c, precipitacion_mm)
        VALUES (%s, NOW(), %s, %s)
    """
    with conn.cursor() as cur:
        try:
            cur.execute(sql, (parcela_id, clima['temp'], clima['lluvia']))
            conn.commit()
            print(f"   ✅ Guardado: {clima['temp']}°C | {clima['lluvia']}mm")
        except Exception as e:
            conn.rollback()
            print(f"   ❌ Error al guardar: {e}")

def main():
    print(f"--- INICIO INGESTA CLIMA ({datetime.now()}) ---")
    try:
        conn = get_db_connection()
        parcelas = obtener_coordenadas_parcelas(conn)
        
        if not parcelas:
            print("📭 No se encontraron parcelas con geolocalización.")
            return

        for id_p, nombre, lat, lon in parcelas:
            print(f"🌍 Procesando {nombre}...")
            datos_clima = consultar_clima(lat, lon)
            if datos_clima:
                guardar_datos(conn, id_p, datos_clima)
            time.sleep(1) # Delay cortesía API

    except Exception as e:
        print(f"❌ Error crítico: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("--- PROCESO FINALIZADO ---")

if __name__ == '__main__':
    main()