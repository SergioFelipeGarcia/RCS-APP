
import duckdb
import os
from typing import List, Dict, Any

# Define la ruta del archivo de la base de datos DuckDB.
# Este archivo DEBE estar excluido en .gitignore (como ya lo hicimos).
DB_PATH = 'rcs_data.duckdb'

def initialize_db():
    """
    Conecta a la base de datos DuckDB y crea la tabla 'transactions' si no existe.
    Esta tabla almacena los mensajes enviados y el estado de la respuesta del webhook.
    """
    print(f"[{os.getpid()}] Inicializando base de datos en: {DB_PATH}")

    # Establece la conexión a DuckDB. Si el archivo no existe, lo crea automáticamente.
    try:
        conn = duckdb.connect(database=DB_PATH)

        # SQL para crear la tabla de transacciones.
        # Es idempotente (solo crea la tabla si no existe).
        create_table_query = """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id VARCHAR PRIMARY KEY,  -- ID único de la transacción (Ej: MSG-12345)
            phone_number VARCHAR NOT NULL,       -- Número de teléfono del destinatario
            message_content VARCHAR,             -- Contenido del mensaje inicial
            status VARCHAR NOT NULL,             -- Estado actual (PENDING, SENT, COMPLETED, FAILED)
            sent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Hora de envío desde Streamlit
            webhook_response_json JSON,          -- Respuesta JSON completa del Webhook
            response_timestamp TIMESTAMP         -- Hora en que llegó la respuesta del Webhook
        );
        """
        conn.execute(create_table_query)
        conn.close()
        print(f"[{os.getpid()}] Base de datos inicializada y tabla 'transactions' verificada.")
        return True
    except Exception as e:
        print(f"Error al inicializar DuckDB: {e}")
        return False

def get_db_connection():
    """Retorna un objeto de conexión DuckDB."""
    return duckdb.connect(database=DB_PATH)

def fetch_all_transactions() -> List[Dict[str, Any]]:
    """
    Recupera todas las transacciones de la base de datos.
    Se usa principalmente en Streamlit para mostrar el historial.
    """
    conn = get_db_connection()
    try:
        # Recupera los datos y los ordena por tiempo de envío descendente
        result = conn.execute("SELECT * FROM transactions ORDER BY sent_timestamp DESC").fetchall()
        
        # Obtiene los nombres de las columnas para crear una lista de diccionarios
        column_names = [desc[0] for desc in conn.description]
        
        # Convierte los resultados de tuplas a una lista de diccionarios
        transactions_list = [dict(zip(column_names, row)) for row in result]
        
        return transactions_list
    finally:
        conn.close()

# ----------------------------------------------------
# Nota: Funciones como 'insert_transaction' y 'update_transaction_status'
# se añadirán cuando desarrollemos el código de Streamlit y Flask.
# ----------------------------------------------------

if __name__ == '__main__':
    # Esta sección permite probar la inicialización ejecutando el archivo directamente.
    print("--- Prueba de Inicialización de DuckDB ---")
    if initialize_db():
        conn = get_db_connection()
        print(f"Número de filas en 'transactions': {conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]}")
        conn.close()
        print("Prueba finalizada.")
    print("------------------------------------------")
