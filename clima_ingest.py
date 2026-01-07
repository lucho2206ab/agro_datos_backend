import os
import psycopg2
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ==========================================
# 📍 COORDENADAS DE LUJÁN DE CUYO, MENDOZA
# ==========================================
LAT_LUJAN = -33.035
LON_LUJAN = -68.878

COORDENADAS_ESTACIONES = [
    (1, LAT_LUJAN, LON_LUJAN),        # Estación 1 en Luján
    (2, LAT_LUJAN + 0.002, LON_LUJAN + 0.002) # Estación 2
]

DELTA = 0.001 

def get_db_connection():
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT", "5432")

    connection_uri = (
        f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        "?sslmode=require"
    )
    return psycopg2.connect(connection_uri)

def crear_poligono_wkt(lat, lon):
    p1 = f"{lon - DELTA} {lat - DELTA}"
    p2 = f"{lon - DELTA} {lat + DELTA}"
    p3 = f"{lon + DELTA} {lat + DELTA}"
    p4 = f"{lon + DELTA} {lat - DELTA}"
    return f"POLYGON(({p1}, {p2}, {p3}, {p4}, {p1}))"

def cargar_coordenadas():
    print(f"--- CONFIGURANDO GEOMETRÍA EN LUJÁN DE CUYO ---")
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # PASO 1: Detectar dónde está instalado PostGIS (Fix definitivo)
        print("Detectando ubicación de PostGIS...")
        cur.execute("""
            SELECT n.nspname 
            FROM pg_proc p 
            JOIN pg_namespace n ON p.pronamespace = n.oid 
            WHERE p.proname = 'st_geomfromtext' 
            LIMIT 1;
        """)
        res = cur.fetchone()
        schema_postgis = res[0] if res else 'public'
        print(f"✅ PostGIS detectado en el esquema: '{schema_postgis}'")

        # PASO 2: Cargar coordenadas usando el esquema detectado
        for id_parcela, lat, lon in COORDENADAS_ESTACIONES:
            poligono_wkt = crear_poligono_wkt(lat, lon)
            print(f"📍 Ubicando Parcela ID {id_parcela}...")
            
            # Construimos la llamada dinámica: esquema.ST_GeomFromText
            sql = f"""
                INSERT INTO geolocalizacion_parcelas (parcela_id, geometria_poligono)
                VALUES (%s, {schema_postgis}.ST_GeomFromText(%s::text, 4326))
                ON CONFLICT (parcela_id) 
                DO UPDATE SET geometria_poligono = EXCLUDED.geometria_poligono;
            """
            cur.execute(sql, (id_parcela, poligono_wkt))
        
        conn.commit()
        print("\n✅ ¡Éxito! Luján de Cuyo ha sido geolocalizado correctamente.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    cargar_coordenadas()