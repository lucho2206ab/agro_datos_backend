from flask import Flask, request, jsonify
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime
import pytz 

load_dotenv()
app = Flask(__name__)

def get_db_connection():
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT")
    
    connection_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
    return psycopg2.connect(connection_uri)

@app.route('/api/lectura', methods=['POST'])
def recibir_lectura():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No se recibió JSON"}), 400

    sensor_id = data.get('sensor_id')
    humedad = data.get('humedad')
    temperatura = data.get('temperatura', 25.0) 
    
    # Validamos explícitamente contra None para permitir el valor 0
    if sensor_id is None or humedad is None:
        return jsonify({"error": "Faltan datos requeridos (sensor_id o humedad)"}), 400

    # Manejo de zona horaria de Argentina
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_hora_ar = datetime.now(tz_ar)

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        sql = """
        INSERT INTO lectura_sensores (sensor_id, fecha_hora, humedad_suelo, temperatura_ambiente)
        VALUES (%s, %s, %s, %s);
        """
        cur.execute(sql, (sensor_id, fecha_hora_ar, humedad, temperatura))
        conn.commit()
        cur.close()
        return jsonify({
            "mensaje": "Datos guardados", 
            "hora_registrada": fecha_hora_ar.strftime('%Y-%m-%d %H:%M:%S')
        }), 201

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)