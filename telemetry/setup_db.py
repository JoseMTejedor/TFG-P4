import sqlite3
import os

# Archivo de la base de datos
DB_FILE = "telemetry.db"

def init_database():
    # Si la base de datos existe en nuestra carpeta, la borramos para empezar de cero las pruebas
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print("Base de datos antigua eliminada.")

    # Al conectar SQLite crea el archivo automáticamente si no existe
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Creamos la tabla
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS link_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
                   
            switch_id INTEGER NOT NULL,
            prev_switch_id INTEGER NOT NULL,
            ingress_egress_time INTEGER NOT NULL,
            queue_time INTEGER NOT NULL,
            accum_time INTEGER NOT NULL,
            link_time INTEGER NOT NULL,
            egress_port INTEGER NOT NULL,
            q_depth INTEGER NOT NULL,
                   
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Guardamos los cambios y cerramos
    conn.commit()
    conn.close()
    
    print("Base de datos 'telemetry.db' creada con éxito.")

if __name__ == '__main__':
    init_database()