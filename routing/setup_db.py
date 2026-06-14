import sqlite3
import os

# Archivo de la base de datos
DB_FILE = "telemetry.db"

# Función para borrar la base de datos antigua
def remove_old_database():
    files_to_remove = [
        DB_FILE,
        DB_FILE + "-wal",
        DB_FILE + "-shm"
    ]

    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
            print(f"Archivo eliminado: {file}")

def init_database():
    # Si la base de datos existe en nuestra carpeta, la borramos para empezar de cero las pruebas
    if os.path.exists(DB_FILE):
        # Eliminamos la base de datos y los ficheros auxiliares de WAL
        remove_old_database()

    # Al conectar SQLite crea el archivo automáticamente si no existe
    conn = sqlite3.connect(DB_FILE)
    
    # Configuramos el modo WAL para mejorar la concurrencia
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout = 2000')
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
            src_ip INTEGER NOT NULL,
            dst_ip INTEGER NOT NULL,
                   
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Guardamos los cambios y cerramos
    conn.commit()
    conn.close()
    
    print("Base de datos 'telemetry.db' creada con éxito.")

if __name__ == '__main__':
    init_database()