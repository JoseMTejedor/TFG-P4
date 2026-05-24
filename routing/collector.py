import socket
import struct
import sqlite3

# Configuración
UDP_IP = "10.99.0.100" # La IP de h_col
UDP_PORT = 8192        # El puerto que pusimos en P4
DB_FILE = "telemetry.db" 

# El formato '! B B I I I I H I' significa:
            # ! -> Network order, Big-Endian. Para especificar que lea los datos de izquierda a derecha
            # B -> Unsigned char (1 byte / 8 bits) -> switch_id
            # B -> Unsigned char (1 byte / 8 bits) -> prev_switch_id
            # I -> Unsigned int (4 bytes / 32 bits) -> ingress_egress_time
            # I -> Unsigned int (4 bytes / 32 bits) -> queue_time
            # I -> Unsigned int (4 bytes / 32 bits) -> accum_time
            # I -> Unsigned int (4 bytes / 32 bits) -> link_time
            # H -> Unsigned short (2 bytes / 16 bits) -> egress_port
            # I -> Unsigned int (4 bytes / 32 bits) -> q_depth
            # I -> Unsigned int (4 bytes / 32 bits) -> src_ip
            # I -> Unsigned int (4 bytes / 32 bits) -> dst_ip
TELEMETRY_FORMAT = "!BBIIIIHIII"
TELEMETRY_SIZE = struct.calcsize(TELEMETRY_FORMAT)

# Convierte una dirección IPv4 almacenada como entero 
# al formato IP habitual.
def int_to_ip(ip_int):
    # struct.pack("!I", ip_int) convierte el entero en 4 bytes en orden de red.
    # socket.inet_ntoa(...) interpreta esos 4 bytes como una dirección IPv4.
    return socket.inet_ntoa(struct.pack("!I", ip_int))


def start_collector():
    # Abrimos el puerto UDP para escuchar

    # Creación del socket
    # Se solicita al sistema operativo el uso de la interfaz de red especificando 
    # el uso de direcciones IPv4 (AF_INET) y el protocolo UDP (SOCK_DGRAM).
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # # Se asocia el socket a la IP y puerto local definidos. 
    # Esto registra el proceso en el sistema operativo para que desvíe 
    # hacia este script cualquier datagrama UDP entrante dirigido al puerto 8192.
    sock.bind((UDP_IP, UDP_PORT))
    print(f"h_col escuchando telemetría en {UDP_IP}:{UDP_PORT}")

    # Nos conectamos a la base de datos
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Creamos un bucle infinito para capturar los paquetes
    try:
        while True:
            # Esperamos a que llegue un paquete 
            # Guardando su contenido en data
            # y la direccion del host de origen en addr
            data, addr = sock.recvfrom(1024)
            
            # Decodificamos los 32 bytes de telemetry_t
            if len(data) == TELEMETRY_SIZE:
                unpacked_data = struct.unpack(TELEMETRY_FORMAT, data)
                sw_id = unpacked_data[0]
                prev_id = unpacked_data[1]
                ingress_egress_time = unpacked_data[2]
                queue_time = unpacked_data[3]
                accum_time = unpacked_data[4]
                link_time = unpacked_data[5]
                egress_port = unpacked_data[6]
                q_depth = unpacked_data[7]
                src_ip = unpacked_data[8]
                dst_ip = unpacked_data[9]

                # Representamos las direcciones IP para el print en 
                # formato x.x.x.x.
                src_ip_str = int_to_ip(src_ip)
                dst_ip_str = int_to_ip(dst_ip)

                print(
                    f"Paquete de s{sw_id} "
                    f"(viene de s{prev_id}) -> "
                    f"IngressEgress:{ingress_egress_time} "
                    f"Queue:{queue_time} "
                    f"Acc:{accum_time} "
                    f"Link:{link_time} "
                    f"EgressPort:{egress_port} "
                    f"QDepth:{q_depth} "
                    f"SRC_ip:{src_ip_str} "
                    f"DST_ip:{dst_ip_str}"
                )

                # Guardamos en base de datos (Consulta parametrizada)
                # Se usan marcadores '?' en lugar de insertar las variables directamente 
                # en la consulta SQL con f-strings. Se implementa de esta forma para
                # evitar vulnerabilidades de inyección SQL. Así nos aseguramos de que
                # cualquier paquete anómalo o manipulado que llegue desde el switch se trate
                # como un dato inofensivo y nunca como código ejecutable.
                cursor.execute('''
                    INSERT INTO link_metrics (
                               switch_id, 
                               prev_switch_id, 
                               ingress_egress_time,
                               queue_time, 
                               accum_time, 
                               link_time,
                               egress_port,
                               q_depth,
                               src_ip,
                               dst_ip
                            )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        sw_id, 
                        prev_id, 
                        ingress_egress_time,
                        queue_time, 
                        accum_time, 
                        link_time,
                        egress_port,
                        q_depth,
                        src_ip,
                        dst_ip
                    )
                )
                conn.commit()
            else:
                print(f"Paquete ignorado (tamaño incorrecto: {len(data)} bytes)")

    except KeyboardInterrupt:
        print("\n Apagando recolector...")
    finally:
        conn.close()
        sock.close()

if __name__ == '__main__':
    start_collector()