import os
import requests
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import json

load_dotenv()

# --- CONFIGURACIÓN ---
ESTACION_ID = 12
PARCELA_ID = 1
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
    """Obtiene clima actual desde API oficial del Gobierno de Mendoza"""
    print(f"[{datetime.now()}] Solicitando clima a API Gobierno Mendoza (Estación {ESTACION_ID})...")
    
    try:
        params = {"estacion": ESTACION_ID}
        response = requests.get(API_URL, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                registro = data[0]
            elif isinstance(data, dict):
                registro = data
            else:
                print("❌ Formato de respuesta no esperado")
                return None
            
            temperatura = float(registro.get("tempAire", 0.0))
            humedad = float(registro.get("humedad", 0.0))
            precipitacion = float(registro.get("precipitacion", 0.0))
            
            print(f"✓ Datos obtenidos:")
            print(f"  - Temperatura: {temperatura}°C")
            print(f"  - Humedad: {humedad}%")
            print(f"  - Precipitación: {precipitacion}mm")
            
            return {
                "temp": temperatura,
                "humedad": humedad,
                "lluvia": precipitacion
            }
        
        else:
            print(f"❌ Error API: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def obtener_hora_local_argentina():
    """Obtiene hora local de Argentina"""
    try:
        tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora_ar = datetime.now(tz_ar)
        return ahora_ar.replace(tzinfo=None)
    except:
        return datetime.now()

def obtener_fecha_hoy():
    """Obtiene la fecha de hoy (sin hora) en Argentina"""
    ahora = obtener_hora_local_argentina()
    return ahora.date()

def verificar_si_existe_hoy(conn, fecha_hoy):
    """Verifica si ya existe un registro para hoy"""
    try:
        cur = conn.cursor()
        
        sql = """
        SELECT COUNT(*) FROM dato_clima 
        WHERE parcela_id = %s 
        AND DATE(fecha_hora) = %s
        """
        
        cur.execute(sql, (PARCELA_ID, fecha_hoy))
        resultado = cur.fetchone()
        cantidad = resultado[0] if resultado else 0
        
        return cantidad > 0
    except Exception as e:
        print(f"⚠️ Error verificando existencia: {e}")
        return False

def obtener_promedio_hoy(conn, fecha_hoy):
    """Obtiene el promedio de mediciones de hoy"""
    try:
        cur = conn.cursor()
        
        sql = """
        SELECT 
            AVG(temperatura_c) as temp_prom,
            AVG(humedad_ambiente) as humedad_prom,
            SUM(precipitacion_mm) as precip_total,
            COUNT(*) as cantidad_registros
        FROM dato_clima 
        WHERE parcela_id = %s 
        AND DATE(fecha_hora) = %s
        """
        
        cur.execute(sql, (PARCELA_ID, fecha_hoy))
        resultado = cur.fetchone()
        
        if resultado:
            return {
                "temp_prom": float(resultado[0]) if resultado[0] else 0,
                "humedad_prom": float(resultado[1]) if resultado[1] else 0,
                "precip_total": float(resultado[2]) if resultado[2] else 0,
                "cantidad": resultado[3]
            }
        return None
    except Exception as e:
        print(f"⚠️ Error obteniendo promedio: {e}")
        return None

def guardar_clima_con_promedio():
    """
    Estrategia mejorada:
    1. Guarda cada lectura instantánea (cada 4 horas)
    2. Al final del día, calcula promedio
    3. Permite ver granularidad horaria si se necesita
    """
    clima = obtener_clima_gobierno()
    
    if not clima:
        print("⚠️ No se pudo obtener datos del clima. Abortando.")
        return False

    fecha_hoy = obtener_fecha_hoy()
    ahora = obtener_hora_local_argentina()

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # PASO 1: Guardar la lectura instantánea
        print(f"\n📊 GUARDANDO LECTURA INSTANTÁNEA")
        print(f"   Fecha/Hora: {ahora.strftime('%Y-%m-%d %H:%M:%S')}")
        
        sql_insert = """
        INSERT INTO dato_clima (parcela_id, fecha_hora, temperatura_c, precipitacion_mm, humedad_ambiente)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        cur.execute(sql_insert, (
            PARCELA_ID,
            ahora,
            clima['temp'],
            clima['lluvia'],
            clima['humedad']
        ))
        conn.commit()
        
        print(f"✅ Lectura instantánea guardada")
        print(f"   Temp: {clima['temp']}°C | Humedad: {clima['humedad']}% | Lluvia: {clima['lluvia']}mm")
        
        # PASO 2: Obtener promedio del día
        print(f"\n📈 PROMEDIO DEL DÍA ({fecha_hoy})")
        
        promedio = obtener_promedio_hoy(conn, fecha_hoy)
        
        if promedio:
            print(f"   Cantidad de muestras: {promedio['cantidad']}")
            print(f"   Temperatura promedio: {promedio['temp_prom']:.1f}°C")
            print(f"   Humedad promedio: {promedio['humedad_prom']:.1f}%")
            print(f"   Precipitación TOTAL: {promedio['precip_total']:.1f}mm")
            
            # Si tienes 4 muestras (día completo), podrías hacer algo especial
            if promedio['cantidad'] == 4:
                print(f"\n✨ DÍA COMPLETO (4 muestras)")
                print(f"   Recomendación: Usar promedios para análisis")
        
        return True
        
    except psycopg2.IntegrityError as e:
        print(f"⚠️ Registro duplicado (ya existe): {e}")
        conn.rollback()
        return True  # No es error crítico
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
    success = guardar_clima_con_promedio()
    exit(0 if success else 1)