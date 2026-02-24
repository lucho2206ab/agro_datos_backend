from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
from datetime import datetime
import pytz
import logging
from functools import wraps

load_dotenv()

app = Flask(__name__)

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar logging a archivo
handler = logging.FileHandler('sensor_data.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- CONFIGURACIÓN ---
API_KEY = os.getenv("API_KEY", "default_key")
ALLOWED_SENSORS = [1, 2, 3, 4, 5]  # IDs de sensores permitidos

def get_db_connection():
    try:
        db_host = os.getenv("DB_HOST")
        db_pass = os.getenv("DB_PASS")
        db_user = os.getenv("DB_USER")
        db_name = os.getenv("DB_NAME")
        db_port = os.getenv("DB_PORT", "5432")
        connection_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
        return psycopg2.connect(connection_uri)
    except Exception as e:
        logger.error(f"DB Connection Error: {str(e)}")
        raise

# --- AUTENTICACIÓN ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            logger.warning("Request sin API Key")
            return jsonify({"error": "Missing X-API-Key header"}), 401
        
        if api_key != API_KEY:
            logger.warning(f"Invalid API Key attempted: {api_key[:4]}...")
            return jsonify({"error": "Invalid API Key"}), 401
        
        return f(*args, **kwargs)
    return decorated_function

# --- VALIDACIONES ---
def validar_dato(sensor_id, humedad, temperatura=None):
    """Retorna (es_valido, mensaje_error)"""
    
    if not isinstance(sensor_id, int) or sensor_id <= 0:
        return False, "sensor_id debe ser un entero positivo"
    
    if sensor_id not in ALLOWED_SENSORS:
        return False, f"sensor_id {sensor_id} no autorizado"
    
    if not isinstance(humedad, (int, float)):
        return False, "humedad debe ser numérica"
    
    if humedad < 0 or humedad > 100:
        return False, f"humedad fuera de rango (0-100): {humedad}"
    
    if temperatura is not None:
        if not isinstance(temperatura, (int, float)):
            return False, "temperatura debe ser numérica"
        if temperatura < -50 or temperatura > 60:
            return False, f"temperatura fuera de rango (-50 a 60): {temperatura}"
    
    return True, None

# Rutas basicas 

@app.route("/")
def home():
    return "AgroDatos backend activo", 200


@app.route("/ping")
def ping():
    return jsonify({"status": "ok"}), 200

# Endpoint del sensor

@app.route('/api/lectura', methods=['POST'])
@require_api_key
def recibir_lectura():
    """
    Endpoint para recibir datos de sensores.
    Soporta array de lecturas con timestamp real o sin él.
    """
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("POST sin JSON")
            return jsonify({"error": "No se recibió JSON"}), 400
        
        # Soportar array o objeto único
        lecturas = data if isinstance(data, list) else [data]
        
        if len(lecturas) > 100:
            logger.warning(f"Intento de enviar {len(lecturas)} lecturas (máx 100)")
            return jsonify({"error": "Máximo 100 lecturas por request"}), 400
        
        resultados = []
        errores = []
        
        for idx, lectura in enumerate(lecturas):
            sensor_id = lectura.get('sensor_id')
            humedad = lectura.get('humedad')
            temperatura = lectura.get('temperatura')
            timestamp_unix = lectura.get('timestamp')  # Timestamp del ESP32
            
            # Validar
            es_valido, error_msg = validar_dato(sensor_id, humedad, temperatura)
            
            if not es_valido:
                errores.append({
                    "index": idx,
                    "error": error_msg,
                    "sensor_id": sensor_id
                })
                logger.warning(f"Dato inválido: {error_msg} | sensor_id={sensor_id}")
                continue
            
            # Insertar en BD
            try:
                tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
                
                # Si el ESP32 envió timestamp, usarlo. Si no, usar hora actual del servidor
                if timestamp_unix:
                    fecha_hora = datetime.fromtimestamp(timestamp_unix, tz=tz_ar).replace(tzinfo=None)
                    logger.info(f"Usando timestamp del ESP32: {fecha_hora}")
                else:
                    fecha_hora = datetime.now(tz_ar).replace(tzinfo=None)
                    logger.info(f"Usando timestamp del servidor: {fecha_hora}")
                
                conn = get_db_connection()
                cur = conn.cursor()
                
                sql = """
                INSERT INTO lectura_sensores 
                (sensor_id, fecha_hora, humedad_suelo, temperatura_ambiente)
                VALUES (%s, %s, %s, %s)
                RETURNING id_lectura, fecha_hora;
                """
                cur.execute(sql, (sensor_id, fecha_hora, humedad, temperatura))
                result = cur.fetchone()
                conn.commit()
                cur.close()
                conn.close()
                
                resultado_ok = {
                    "sensor_id": sensor_id,
                    "humedad": humedad,
                    "registro_id": result[0],
                    "timestamp": result[1].isoformat(),
                    "timestamp_fuente": "esp32" if timestamp_unix else "servidor"
                }
                resultados.append(resultado_ok)
                
                logger.info(f"Lectura OK: sensor={sensor_id}, humedad={humedad}%, id={result[0]}")
                
            except Exception as e:
                errores.append({
                    "index": idx,
                    "error": f"DB Error: {str(e)}",
                    "sensor_id": sensor_id
                })
                logger.error(f"DB Error para sensor {sensor_id}: {str(e)}")
        
        # Respuesta
        status_code = 201 if len(resultados) > 0 else 400
        
        response = {
            "status": "success" if len(resultados) > 0 else "partial_error",
            "insertados": len(resultados),
            "rechazados": len(errores),
            "datos": resultados
        }
        
        if errores:
            response["errores"] = errores
        
        return jsonify(response), status_code

    except Exception as e:
        logger.error(f"Unhandled error en /api/lectura: {str(e)}")
        return jsonify({"error": "Server error", "detail": str(e)}), 500

@app.route('/api/salud', methods=['GET'])
def salud():
    """Endpoint de health check"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/api/sensores/estado', methods=['GET'])
@require_api_key
def estado_sensores():
    """
    Retorna el estado del último reporte de cada sensor.
    Útil para detectar sensores offline.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        sql = """
        SELECT 
            sensor_id,
            MAX(fecha_hora) as ultimo_reporte,
            COUNT(*) as total_registros,
            AVG(humedad_suelo) as humedad_promedio,
            EXTRACT(EPOCH FROM (NOW() - MAX(fecha_hora))) / 3600 as horas_sin_reportar
        FROM lectura_sensores
        WHERE sensor_id = ANY(%s)
        GROUP BY sensor_id
        ORDER BY sensor_id;
        """
        
        cur.execute(sql, (ALLOWED_SENSORS,))
        resultados = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "sensores": [dict(r) for r in resultados]
        }), 200
        
    except Exception as e:
        logger.error(f"Error en estado_sensores: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"500 Error: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)