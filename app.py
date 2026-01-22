import os
import logging
import psycopg2
import pytz
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURACIÓN Y LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY", "mi_clave_secreta_123")
ALLOWED_SENSORS = [1, 2, 3, 4, 5]

def get_db_connection():
    try:
        connection = psycopg2.connect(os.getenv("DATABASE_URL") or f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?sslmode=require")
        return connection
    except Exception as e:
        logger.error(f"Error de conexión a DB: {e}")
        return None

# --- DECORADOR PARA SEGURIDAD ---
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key')
        if key and key == API_KEY:
            return f(*args, **kwargs)
        logger.warning(f"Intento de acceso no autorizado desde: {request.remote_addr}")
        return jsonify({"error": "No autorizado"}), 401
    return decorated

# --- VALIDACIÓN ---
def es_dato_valido(s_id, hum):
    if s_id not in ALLOWED_SENSORS: return False
    if not (0 <= hum <= 100): return False
    return True

@app.route('/api/lectura', methods=['POST'])
@require_api_key
def recibir_lectura():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No hay datos"}), 400

    # Convertir a lista si es un solo objeto
    lecturas = data if isinstance(data, list) else [data]
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora = datetime.now(tz_ar)
    
    conn = get_db_connection()
    if not conn: return jsonify({"error": "Error de base de datos"}), 500
    
    insertados = 0
    try:
        cur = conn.cursor()
        for l in lecturas:
            s_id = l.get('sensor_id')
            hum = l.get('humedad')
            # Si viene de una ráfaga, restamos el offset para tener la hora real de la medición
            offset = l.get('offset_segundos', 0)
            fecha_medicion = ahora - timedelta(seconds=offset)

            if es_dato_valido(s_id, hum):
                cur.execute(
                    "INSERT INTO lectura_sensores (sensor_id, fecha_hora, humedad_suelo) VALUES (%s, %s, %s)",
                    (s_id, fecha_medicion.replace(tzinfo=None), hum)
                )
                insertados += 1
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "insertados": insertados}), 201
    except Exception as e:
        logger.error(f"Error al insertar: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/salud', methods=['GET'])
def salud():
    return jsonify({"estado": "online", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))