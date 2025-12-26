# app.py (Ejemplo simplificado)
from flask import Flask, request, jsonify
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

# Función para conectar a Supabase
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )
    return conn

# API Endpoint para recibir datos del sensor (POST request)
@app.route('/api/lectura', methods=['POST'])
def recibir_lectura():
    # 1. Obtener datos del cuerpo de la solicitud (Arduino)
    data = request.get_json()
    
    # Validaciones (Asegúrate que estos campos existen en el JSON del Arduino)
    sensor_id = data.get('sensor_id')
    humedad = data.get('humedad')
    temperatura = data.get('temperatura')
    # fecha_hora lo registraremos en el servidor para mayor precisión
    
    if not all([sensor_id, humedad, temperatura]):
        return jsonify({"error": "Faltan datos requeridos"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 2. Insertar datos en la tabla 'lecturas_sensores'
        # ¡IMPORTANTE! Ajusta esta consulta a la estructura exacta de tu tabla
        sql = """
        INSERT INTO lectura_sensores (sensor_id, fecha_hora, humedad_suelo, temperatura_ambiente)
        VALUES (%s, NOW(), %s, %s);
        """
        cur.execute(sql, (sensor_id, humedad, temperatura))
        conn.commit()
        return jsonify({"mensaje": "Datos recibidos e insertados correctamente"}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True) # debug=True solo para desarrollo