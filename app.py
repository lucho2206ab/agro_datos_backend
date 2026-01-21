from flask import Flask, request, jsonify
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pytz 

load_dotenv()

app = Flask(__name__)

def get_db_connection():
    db_host = os.getenv("DB_HOST")
    db_pass = os.getenv("DB_PASS")
    db_user = os.getenv("DB_USER")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT", "5432")
    connection_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?sslmode=require"
    return psycopg2.connect(connection_uri)

@app.route('/api/lectura', methods=['POST'])
def recibir_lectura():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibió JSON"}), 400

    # Si recibimos un solo objeto, lo convertimos en lista para usar la misma lógica
    if not isinstance(data, list):
        payload = [data]
    else:
        payload = data

    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora_ar = datetime.now(tz_ar)
    
    conn = None
    registros_exitosos = 0
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        for lectura in payload:
            sensor_id = lectura.get('sensor_id')
            humedad = lectura.get('humedad')
            temperatura = lectura.get('temperatura')
            # 'offset_segundos' es cuánto tiempo atrás ocurrió esta lectura respecto a ahora
            offset_segundos = int(lectura.get('offset_segundos', 0)) 
            
            # Calculamos la hora real de esa medición específica
            fecha_hora_lectura = ahora_ar - timedelta(seconds=offset_segundos)
            # Quitamos la info de zona horaria para insertar en la DB (Timestamp without timezone)
            fecha_final = fecha_hora_lectura.replace(tzinfo=None)

            sql = """
            INSERT INTO lectura_sensores (sensor_id, fecha_hora, humedad_suelo, temperatura_ambiente)
            VALUES (%s, %s, %s, %s);
            """
            cur.execute(sql, (sensor_id, fecha_final, humedad, temperatura))
            registros_exitosos += 1
            
        conn.commit()
        cur.close()

        return jsonify({
            "status": "success",
            "mensaje": f"Se procesaron {registros_exitosos} lecturas correctamente",
            "ultima_hora_servidor": ahora_ar.strftime('%Y-%m-%d %H:%M:%S')
        }), 201

    except Exception as e:
        if conn: conn.rollback()
        print(f"Error procesando ráfaga: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)