import os
import requests
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

load_dotenv()

ESTACION_ID = 12
PARCELA_ID = 1
API_URL = "https://agrometeo.mendoza.gov.ar/api/getUltimasInstantaneas.php"


def get_db_connection():

    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT", "5432")

    uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"

    return psycopg2.connect(uri)


def hora_argentina():

    tz = pytz.timezone("America/Argentina/Buenos_Aires")

    ahora = datetime.now(tz)

    return ahora.replace(tzinfo=None)


def obtener_clima():

    try:

        params = {"estacion": ESTACION_ID}

        r = requests.get(API_URL, params=params, timeout=15)

        if r.status_code != 200:
            return None

        data = r.json()

        if isinstance(data, list):
            registro = data[0]
        else:
            registro = data

        return {
            "temp": float(registro.get("tempAire", 0)),
            "humedad": float(registro.get("humedad", 0)),
            "lluvia": float(registro.get("precipitacion", 0))
        }

    except Exception as e:

        print("Error API:", e)

        return None


def obtener_ultima_lectura(conn):

    cur = conn.cursor()

    sql = """
    SELECT fecha_hora, precipitacion_mm
    FROM dato_clima
    WHERE parcela_id=%s
    ORDER BY fecha_hora DESC
    LIMIT 1
    """

    cur.execute(sql, (PARCELA_ID,))

    row = cur.fetchone()

    if row:

        return {
            "fecha": row[0],
            "lluvia": float(row[1])
        }

    return None


def calcular_lluvia_intervalo(conn, lluvia_api, ahora):

    ultima = obtener_ultima_lectura(conn)

    if ultima is None:
        return lluvia_api, ahora

    lluvia_anterior = ultima["lluvia"]

    lluvia_intervalo = lluvia_api - lluvia_anterior

    if lluvia_intervalo < 0:
        lluvia_intervalo = lluvia_api

    fecha_guardado = ahora

    # ------------------------
    # Corrección Agrometeo
    # ------------------------

    if ahora.hour <= 8 and lluvia_intervalo > 0:

        print("🌧️ Lluvia detectada temprano → probablemente del día anterior")

        fecha_guardado = ahora - timedelta(hours=12)

    return lluvia_intervalo, fecha_guardado


def guardar_clima():

    clima = obtener_clima()

    if not clima:
        print("No se obtuvo clima")
        return False

    ahora = hora_argentina()

    conn = None

    try:

        conn = get_db_connection()

        lluvia_real, fecha_guardado = calcular_lluvia_intervalo(
            conn,
            clima["lluvia"],
            ahora
        )

        cur = conn.cursor()

        sql = """
        INSERT INTO dato_clima
        (parcela_id, fecha_hora, temperatura_c, precipitacion_mm, humedad_ambiente)
        VALUES (%s,%s,%s,%s,%s)
        """

        cur.execute(sql, (

            PARCELA_ID,
            fecha_guardado,
            clima["temp"],
            lluvia_real,
            clima["humedad"]

        ))

        conn.commit()

        print("Registro guardado")

        print("Temp:", clima["temp"])
        print("Humedad:", clima["humedad"])
        print("Lluvia:", lluvia_real)

        return True

    except Exception as e:

        print("Error BD:", e)

        if conn:
            conn.rollback()

        return False

    finally:

        if conn:
            conn.close()


if __name__ == "__main__":

    ok = guardar_clima()

    exit(0 if ok else 1)