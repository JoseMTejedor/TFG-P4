import time
import sqlite3
import ipaddress
from dataclasses import dataclass
import networkx as nx
from p4utils.utils.sswitch_p4runtime_API import SimpleSwitchP4RuntimeAPI

# -----------------------------------------------------------------------------
# Parámetros generales del controlador
# -----------------------------------------------------------------------------

P4RT_PATH = 'telemetry_dynamic_p4rt.txt'
JSON_PATH = 'telemetry_dynamic.json'
DB_FILE = 'telemetry.db'

# Coste base por enlace entre switches, 
# La unidad son us.
# Valor estimado a partir de medidas RTT.
BASE_LINK_DELAY = 1030

# Número de muestras usadas para calcular la media del retardo.
# Si para un puerto solo hay 5 muestras y N=30, se divide entre 30 igualmente.
# Evita sobrerreaccionar cuando hay pocos datos.
SAMPLES_PER_PORT = 30

# Ventana temporal usada para calcular las métricas recientes.
METRICS_WINDOW_SECONDS = 30

# Umbral relativo para seleccionar una ruta alternativa.
THRESHOLD = 0.20

# Margen mínimo opcional para evitar cambios por diferencias muy pequeñas.
MIN_IMPROVEMENT = 200

# Tiempo que una ruta dinamica permanece activa antes de comprobar si sigue viva.
ROUTE_TTL = 60
#Tiempo que una ruta espera un nuevo mensaje de flujo vivo antes de considerarla inactiva.
PROBATION_WINDOW = 15

# Tipos de digest definidos en P4.
DIGEST_NEW_FLOW = 1
DIGEST_FLOW_ALIVE = 2

# -----------------------------------------------------------------------------
# Información de switches, hosts y enlaces
# -----------------------------------------------------------------------------

# Es necesario guardar la informaicon de la topología, para poder hacer el 
# calculo de las rutas dinámicas.

# Switches de la topología. La clave del diccionario es el identificador numérico del switch, 
# que coincide con el device_id de P4Runtime, con el switch_id usado en P4 y por ende,
# con el valor almacenado en la base de datos.
SWITCHES = {
    1: {'name': 'sA', 'grpc_port': 9559, 'collector_src_ip': '10.99.0.1'},
    2: {'name': 'sB', 'grpc_port': 9560, 'collector_src_ip': '10.99.0.2'},
    3: {'name': 'sC', 'grpc_port': 9561, 'collector_src_ip': '10.99.0.3'},
    4: {'name': 'sD', 'grpc_port': 9562, 'collector_src_ip': '10.99.0.4'},
    5: {'name': 'sE', 'grpc_port': 9563, 'collector_src_ip': '10.99.0.5'},
    6: {'name': 'sF', 'grpc_port': 9564, 'collector_src_ip': '10.99.0.6'},
    7: {'name': 'sG', 'grpc_port': 9565, 'collector_src_ip': '10.99.0.7'},
}

# Hosts de la topología. La clave del diccionario es la IP del host.
HOSTS = {
    '10.0.1.1': {'name': 'h1', 'switch': 1, 'port': 1, 'mac': '00:00:00:00:00:01'},
    '10.0.1.2': {'name': 'h4', 'switch': 1, 'port': 6, 'mac': '00:00:00:00:00:04'},
    '10.0.3.1': {'name': 'h2', 'switch': 3, 'port': 1, 'mac': '00:00:00:00:00:02'},
    '10.0.4.1': {'name': 'h5', 'switch': 4, 'port': 1, 'mac': '00:00:00:00:00:05'},
    '10.0.4.2': {'name': 'h6', 'switch': 4, 'port': 6, 'mac': '00:00:00:00:00:06'},
    '10.0.5.1': {'name': 'h3', 'switch': 5, 'port': 1, 'mac': '00:00:00:00:00:03'},
}

# Enlaces entre switches.
# La primera clave identifica el switch origen. Dentro de cada entrada aparecen
# los switches vecinos alcanzables directamente desde él.
# Para cada vecino se indica el puerto de salida y la MAC del siguiente salto.
LINKS = {
    1: {
        2: {'port': 2, 'mac': '00:00:00:00:0A:0B'},
        6: {'port': 3, 'mac': '00:00:00:00:0A:0F'},
        7: {'port': 4, 'mac': '00:00:00:00:0A:07'},
    },
    2: {
        1: {'port': 3, 'mac': '00:00:00:00:0B:0A'},
        3: {'port': 2, 'mac': '00:00:00:00:0B:0C'},
    },
    3: {
        2: {'port': 3, 'mac': '00:00:00:00:0C:0B'},
        4: {'port': 2, 'mac': '00:00:00:00:0C:0D'},
    },
    4: {
        3: {'port': 3, 'mac': '00:00:00:00:0D:0C'},
        5: {'port': 2, 'mac': '00:00:00:00:0D:0E'},
        7: {'port': 4, 'mac': '00:00:00:00:0D:07'},
    },
    5: {
        4: {'port': 3, 'mac': '00:00:00:00:0E:0D'},
        6: {'port': 2, 'mac': '00:00:00:00:0E:0F'},
    },
    6: {
        1: {'port': 2, 'mac': '00:00:00:00:0F:0A'},
        5: {'port': 3, 'mac': '00:00:00:00:0F:0E'},
    },
    7: {
        1: {'port': 2, 'mac': '00:00:00:00:07:0A'},
        4: {'port': 3, 'mac': '00:00:00:00:07:0D'},
    },
}

# Data class para guardar el estado de una ruta dinámica.
@dataclass
class RouteState:
    src_ip: str
    dst_ip: str
    path: list
    status: str
    expires_at: float
    probe_until: float = 0.0 #Se inicializa en 0 porque cuando la ruta está activa, no necesitamos el valor.

# -----------------------------------------------------------------------------
# Funciones útiles
# -----------------------------------------------------------------------------

# Función para convertir una IP en formato entero a formato texto.
# La base de datos y los digest reciben las IPs como enteros de 32 bits.
# El controlador trabaja con IPs en formato texto, porque es el que usamos
# para instalar reglas P4Runtime.
def int_to_ip(ip_int):
    return str(ipaddress.IPv4Address(ip_int))

# Genera una clave bidireccional para identificar una pareja de hosts.
# sorted(...) ordena las dos IPs para que A->B y B->A produzcan la misma clave.
# tuple(...) convierte la lista ordenada en una tupla, que puede usarse como
# clave en el diccionario de rutas dinámicas.
def pair_key(src_ip, dst_ip):
    return tuple(sorted([src_ip, dst_ip]))

def is_management_traffic(src_ip, dst_ip):
    return src_ip.startswith('10.99.') or dst_ip.startswith('10.99.')

# Los campos enviados por P4Runtime dentro del digest llegan como bytes.
# Esta función interpreta esos bytes en orden de red,
# y los convierte a un entero normal de Python.
def p4data_bitstring_to_int(p4data):
    return int.from_bytes(p4data.bitstring, byteorder='big')

# Extrae los campos de un digest flow_digest_t recibido desde P4Runtime.
# En P4 el digest se define como un struct:
#        digest_type, switch_id, src_ip, dst_ip
# Al llegar p4utils lo entregacomo una entrada de digest. Dentro de esa 
# entrada hay una estructura interna y sus campos aparecen en la lista 
# members, manteniendo el mismo orden definido en P4.
def parse_flow_digest_entry(entry):
    # Obtenemos la estructura interna del digest recibido.
    struct_data = getattr(entry, 'struct')
    # Extraemos los campos de esa estructura.
    members = struct_data.members

    if len(members) != 4:
        raise ValueError(f'Digest inesperado: se esperaban 4 campos y llegaron {len(members)}')

    digest_type = p4data_bitstring_to_int(members[0])
    switch_id = p4data_bitstring_to_int(members[1])
    src_ip = int_to_ip(p4data_bitstring_to_int(members[2]))
    dst_ip = int_to_ip(p4data_bitstring_to_int(members[3]))

    return digest_type, switch_id, src_ip, dst_ip


# -----------------------------------------------------------------------------
# Controlador dinámico
# -----------------------------------------------------------------------------

class DynamicTelemetryController:
    def __init__(self):
        
        # Diccionario donde se guardan las conexiones P4Runtime con cada switch.
        # La clave es el ID numérico del switch y el valor es su controlador.
        self.controllers = {}

        # Grafo de NetworkX que representa la topología de la red.
        # Los nodos son los switches y las aristas son los enlaces.
        # Se usa para calcular caminos entre el switch origen y el switch destino.
        self.graph = nx.Graph()
        
        # Rutas dinámicas instaladas actualmente.
        # La clave es una pareja de IPs ordenada.
        # El valor es un RouteState con el camino elegido y sus temporizadores.
        self.dynamic_routes = {}

    # -------------------------------------------------------------------------
    # Inicialización
    # -------------------------------------------------------------------------
    
    # Recorre todos los switches de la topología, crea una conexión
    # P4Runtime con cada uno y la guarda en self.controllers 
    # usando el ID del switch como clave.
    def connect_switches(self):
        for sw_id, info in SWITCHES.items():
            self.controllers[sw_id] = SimpleSwitchP4RuntimeAPI(
                device_id=sw_id,
                grpc_port=info['grpc_port'],
                p4rt_path=P4RT_PATH,
                json_path=JSON_PATH,
            )
    
    # Configura el estado inicial de todos los switches P4.
    # Se borra cualquier configuración previa con reset_state().
    # Se instalan las reglas comunes necesarias para la telemetría:
    #   - switch_info: asigna el identificador del switch.
    #   - telemetry_routing: cómo enviar los paquetes clonados al colector.
    #   - cs_create: crea la sesión de clonación.
    #   - ipv4_lpm: tabla de encaminamiento estático de respaldo.
    #
    # Se instalan las rutas estáticas iniciales y las reglas que
    # eliminan la cabecera measurement_t antes de entregar paquetes a hosts.
    def reset_and_configure_static_state(self):
        for sw_id, controller in self.controllers.items():
            controller.reset_state()
            #Cambiamos la accion por defecto de la tabla switch_info para añadir el ID del switch.
            controller.table_set_default('switch_info', 'set_switch_id', [str(sw_id)])
            #Cambiamos la accion por defecto de la tabla telemetry_routing para añadir la MAC y la IP de la base de datos.
            controller.table_set_default(
                'telemetry_routing',
                'route_telemetry',
                ['00:00:00:99:99:99', '10.99.0.100', SWITCHES[sw_id]['collector_src_ip']],
            )
            #Indicamos que los mensajes clonados, con ID 500, se manden por el puerto 5.
            controller.cs_create(500, [5])
            controller.table_set_default('ipv4_lpm', 'drop')

        self.install_static_ipv4_routes()
        self.install_remove_header_rules()

    # Habilita en los switches la recepción del digest flow_digest_t.
    # se usa para avisar al controlador de la detección de un nuevo flujo,
    # o confirmar que una ruta dinámica sigue teniendo tráfico.
    def enable_digests(self):
        for sw_id, controller in self.controllers.items():
            controller.digest_enable(
                'flow_digest_t',
                max_timeout_ns=0,
                max_list_size=1,
                ack_timeout_ns=0,
            )
            print(f"Digest flow_digest_t habilitado en {SWITCHES[sw_id]['name']}")
    
    # Construye el grafo de la topología usando NetworkX.
    def build_graph(self):
        # Cada switch se añade como un nodo del grafo.
        for sw_id in SWITCHES:
            self.graph.add_node(sw_id)

        # Se añaden los enlaces entre switches.
        # src_sw es el switch origen y dst_sw cada uno de sus vecinos.
        for src_sw, neighbors in LINKS.items():
            for dst_sw in neighbors:
                # Como el grafo es no dirigido, solo se añade enlace si no existe.
                if not self.graph.has_edge(src_sw, dst_sw):
                    self.graph.add_edge(src_sw, dst_sw, base_cost=BASE_LINK_DELAY)

    # -------------------------------------------------------------------------
    # Configuración estática original
    # -------------------------------------------------------------------------

    def install_static_ipv4_routes(self):
        c = self.controllers

        # Switch A
        c[1].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.1/32'], ['00:00:00:00:00:01', '1'])
        c[1].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.2/32'], ['00:00:00:00:00:04', '6'])
        c[1].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0A:0B', '2'])
        c[1].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0A:07', '4'])
        c[1].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0A:0F', '3'])

        # Switch B
        c[2].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0B:0A', '3'])
        c[2].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0B:0C', '2'])
        c[2].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0B:0C', '2'])
        c[2].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0B:0A', '3'])

        # Switch C
        c[3].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.1/32'], ['00:00:00:00:00:02', '1'])
        c[3].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0C:0B', '3'])
        c[3].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0C:0D', '2'])
        c[3].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0C:0D', '2'])

        # Switch D
        c[4].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.1/32'], ['00:00:00:00:00:05', '1'])
        c[4].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.2/32'], ['00:00:00:00:00:06', '6'])
        c[4].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0D:07', '4'])
        c[4].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0D:0C', '3'])
        c[4].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0D:0E', '2'])

        # Switch E
        c[5].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.1/32'], ['00:00:00:00:00:03', '1'])
        c[5].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0E:0D', '3'])
        c[5].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0E:0D', '3'])
        c[5].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0E:0F', '2'])

        # Switch F
        c[6].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0F:0A', '2'])
        c[6].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0F:0A', '2'])
        c[6].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0F:0E', '3'])
        c[6].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0F:0E', '3'])

        # Switch G
        c[7].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:07:0A', '2'])
        c[7].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:07:0A', '2'])
        c[7].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:07:0D', '3'])
        c[7].table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:07:0D', '3'])

    # Elimina la cabecera personalizada measurement_t antes de entregar paquetes a hosts finales.
    # Para ello se añaden reglas a la tabla remove_header_tbl, indicando el puerto de salida hacia hosts.
    def install_remove_header_rules(self):
        self.controllers[1].table_add('remove_header_tbl', 'remove_header', ['1'])
        self.controllers[1].table_add('remove_header_tbl', 'remove_header', ['6'])
        self.controllers[3].table_add('remove_header_tbl', 'remove_header', ['1'])
        self.controllers[4].table_add('remove_header_tbl', 'remove_header', ['1'])
        self.controllers[4].table_add('remove_header_tbl', 'remove_header', ['6'])
        self.controllers[5].table_add('remove_header_tbl', 'remove_header', ['1'])

    # -------------------------------------------------------------------------
    # Métricas y cálculo de rutas
    # -------------------------------------------------------------------------

    # Lee de la base de datos las métricas recientes de telemetría y las agrupa
    # por puerto de salida.
    # La clave usada para agrupar es (switch_id, egress_port), porque el coste
    # de una ruta depende del puerto por el que sale el paquete en cada switch.
    # Solo se tienen en cuenta muestras dentro de la ventana temporal 
    # METRICS_WINDOW_SECONDS y como máximo las últimas SAMPLES_PER_PORT muestras.
    def read_port_metrics(self, exclude_pair_key=None):

        samples = {}

        try:
            # Se pone el timeout para evitar que se bloquee la lectura si se estaa escribiendo en la base de datos
            conn = sqlite3.connect(DB_FILE, timeout = 2.0)
            conn.execute('PRAGMA busy_timeout = 2000')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT switch_id, egress_port, ingress_egress_time, queue_time, src_ip, dst_ip
                FROM link_metrics
                WHERE timestamp >= datetime('now', ?)
                ORDER BY id DESC
            ''', (f'-{METRICS_WINDOW_SECONDS} seconds',))
            rows = cursor.fetchall()
            conn.close()

        except sqlite3.Error as exc:
            print(f'No se pudieron leer métricas de la base de datos: {exc}')
            return {}

        for sw_id, port, ingress_egress_time, queue_time, src_ip, dst_ip in rows:
            # Las IPs llegan desde la base de datos como enteros.
            # Las convertimos a texto.
            src_ip_text = int_to_ip(src_ip)
            dst_ip_text = int_to_ip(dst_ip)

            # Si estamos calculando la ruta para un par concreto, ignoramos
            # las muestras generadas por ese mismo par en ambos sentidos.
            # Asi se evita a sobrerreaccionar a cambios causados por la propia ruta dinámica que se está evaluando.
            if exclude_pair_key is not None and pair_key(src_ip_text, dst_ip_text) == exclude_pair_key:
                continue

            key = (sw_id, port)

            if key not in samples:
                samples[key] = []

            # Como los datos vienen ordenados por id DESC, nos quedamos con las
            # últimas SAMPLES_PER_PORT muestras de cada puerto.
            if len(samples[key]) < SAMPLES_PER_PORT:
                samples[key].append((ingress_egress_time, queue_time))

        metrics = {}
        
        # Las medias se dividen siempre entre SAMPLES_PER_PORT, para 
        # suaviza el resultado cuando hay pocos datos evitando sobrerreaccionar.
        for key, values in samples.items():
            avg_ingress_egress = sum(v[0] for v in values) / SAMPLES_PER_PORT
            avg_queue = sum(v[1] for v in values) / SAMPLES_PER_PORT

            metrics[key] = {
                'avg_ingress_egress_time': avg_ingress_egress,
                'avg_queue_time': avg_queue,
                'num_samples': len(values),
            }

        return metrics

    # Calcula el coste de usar el enlace.
    # Obtiene el puerto de salida correspondiente y suma
    # al coste base del enlace el retardo medio medido en ese puerto.
    def edge_cost(self, src_sw, dst_sw, metrics):
        out_port = LINKS[src_sw][dst_sw]['port']
        port_metrics = metrics.get((src_sw, out_port), {})
        avg_ingress_egress = port_metrics.get('avg_ingress_egress_time', 0)
        return BASE_LINK_DELAY + avg_ingress_egress

    # Calcula el coste total de una ruta sumando el coste de cada enlace
    # consecutivo entre los switches de la ruta.
    def path_cost(self, path, metrics):
        if len(path) <= 1:
            return 0

        cost = 0
        # zip(path[:-1], path[1:]) genera pares consecutivos de switches en la ruta.
        for src_sw, dst_sw in zip(path[:-1], path[1:]):
            cost += self.edge_cost(src_sw, dst_sw, metrics)
        return cost

    # Devuelve el tiempo medio de cola mas alto encontrado en los puertos
    # de salida que forman la ruta. Sirve para identificar el punto de más
    # congestión del camino.
    def max_queue_on_path(self, path, metrics):
        max_queue = 0
        for src_sw, dst_sw in zip(path[:-1], path[1:]):
            out_port = LINKS[src_sw][dst_sw]['port']
            port_metrics = metrics.get((src_sw, out_port), {})
            max_queue = max(max_queue, port_metrics.get('avg_queue_time', 0))
        return max_queue
    
    # Selecciona la ruta que debe usarse entre dos hosts.
    # Primero calcula la ruta por defecto y su coste actual.
    # Después calcula la mejor ruta según las métricas recientes y su coste.
    # Solo se elige la ruta dinámica si mejora suficientemente a la ruta por defect
    def choose_path(self, src_ip, dst_ip):
        src_sw = HOSTS[src_ip]['switch']
        dst_sw = HOSTS[dst_ip]['switch']
        key = pair_key(src_ip, dst_ip)

        # Si ambos hosts están en el mismo switch, no hay camino interno que calcular.
        if src_sw == dst_sw:
            return [src_sw]

        metrics = self.read_port_metrics(exclude_pair_key=key)

        default_path = nx.shortest_path(self.graph, src_sw, dst_sw, weight='base_cost')
        default_cost = self.path_cost(default_path, metrics)
        default_max_queue = self.max_queue_on_path(default_path, metrics)

        # Actualizamos pesos dinámicos para calcular el mejor camino. actual.
        for u, v in self.graph.edges():
            forward_cost = self.edge_cost(u, v, metrics)
            reverse_cost = self.edge_cost(v, u, metrics)
            # El grafo es no dirigido. Por lo que usamos el peor de ambos
            # sentidos como coste conservador del enlace.
            self.graph[u][v]['dynamic_cost'] = max(forward_cost, reverse_cost)

        best_path = nx.shortest_path(self.graph, src_sw, dst_sw, weight='dynamic_cost')
        best_cost = self.path_cost(best_path, metrics)

        improvement_abs = default_cost - best_cost
        improvement_rel = improvement_abs / default_cost if default_cost > 0 else 0

        print(
            f'Ruta por defecto {default_path}: coste={default_cost:.1f} us, '
            f'max_queue={default_max_queue:.1f} us'
        )
        print(
            f'Mejor ruta dinámica {best_path}: coste={best_cost:.1f} us, '
            f'mejora={improvement_abs:.1f} us ({improvement_rel:.1%})'
        )

        if (
            improvement_rel >= THRESHOLD
            and improvement_abs >= MIN_IMPROVEMENT
        ):
            print('Se selecciona la ruta dinámica alternativa.')
            return best_path

        print('Se mantiene la ruta por defecto/corta.')
        return default_path
    
    # -------------------------------------------------------------------------
    # Instalación, modificación y borrado de rutas dinámicas
    # -------------------------------------------------------------------------

    # Devuelve la MAC y el puerto que debe usar el switch para su siguiente salto,
    # entregandole el path que debe seguir.
    def action_params_for_step(self, dst_ip, path, index):
        current_sw = path[index]

        if index == len(path) - 1:
            # Último switch del camino: reenviar al host destino.
            return HOSTS[dst_ip]['mac'], HOSTS[dst_ip]['port']

        next_sw = path[index + 1]
        link_info = LINKS[current_sw][next_sw]
        return link_info['mac'], link_info['port']

    # Instala las reglas de flow_routing para un sentido del tráfico.
    # Para cada switch se calcula la MAC y el puerto de salida
    # para avanzar al siguiente salto o entregar al host destino.
    def install_direction(self, src_ip, dst_ip, path, action_name='ipv4_forward'):
        for index, sw_id in enumerate(path):
            dst_mac, out_port = self.action_params_for_step(dst_ip, path, index)
            self.controllers[sw_id].table_add(
                'flow_routing',
                action_name,
                [src_ip, dst_ip],
                [dst_mac, str(out_port)],
            )

    # Elimina de flow_routing las reglas instaladas para un sentido concreto
    # del tráfico en todos los switches que forman la ruta.
    def delete_direction(self, src_ip, dst_ip, path):
        for sw_id in path:
            self.controllers[sw_id].table_delete_match(
                'flow_routing',
                [src_ip, dst_ip],
            )

    # Modifica la acción de flow_routing solo en el switch de entrada del camino.
    # Se usa para pasar una ruta a modo probation o devolverla a modo normal.
    def modify_ingress_action(self, src_ip, dst_ip, path, action_name):
        ingress_sw = path[0]
        dst_mac, out_port = self.action_params_for_step(dst_ip, path, 0)
        self.controllers[ingress_sw].table_modify_match(
            'flow_routing',
            action_name,
            [src_ip, dst_ip],
            [dst_mac, str(out_port)],
        )

    # Instala una ruta dinámica en ambos sentidos entre dos hosts.
    # También guarda el estado de la ruta para controlar su tiempo de vida.
    def install_bidirectional_route(self, src_ip, dst_ip, path):
        reverse_path = list(reversed(path))

        self.install_direction(src_ip, dst_ip, path, 'ipv4_forward')
        self.install_direction(dst_ip, src_ip, reverse_path, 'ipv4_forward')

        key = pair_key(src_ip, dst_ip)
        self.dynamic_routes[key] = RouteState(
            src_ip=src_ip,
            dst_ip=dst_ip,
            path=path,
            status='ACTIVE',
            expires_at=time.monotonic() + ROUTE_TTL,
        )

        print(f'Ruta dinámica instalada para {src_ip} <-> {dst_ip}: {path}')

    # Modificamos los switches de entrada de cada sentido para que
    # entren estado probation. Para saber si la ruta sigue activa o no. 
    # Permitiendo que se manden digests.
    def enter_probation(self, state):
        reverse_path = list(reversed(state.path))

        self.modify_ingress_action(state.src_ip, state.dst_ip, state.path, 'ipv4_forward_probe')
        self.modify_ingress_action(state.dst_ip, state.src_ip, reverse_path, 'ipv4_forward_probe')

        state.status = 'PROBATION'
        state.probe_until = time.monotonic() + PROBATION_WINDOW

        print(f'Ruta {state.src_ip} <-> {state.dst_ip} en probation.')

    # Renueva una ruta que estaba en probation porque se ha recibido tráfico nuevo.
    def renew_route(self, state):
        reverse_path = list(reversed(state.path))

        self.modify_ingress_action(state.src_ip, state.dst_ip, state.path, 'ipv4_forward')
        self.modify_ingress_action(state.dst_ip, state.src_ip, reverse_path, 'ipv4_forward')

        state.status = 'ACTIVE'
        state.expires_at = time.monotonic() + ROUTE_TTL
        state.probe_until = 0.0

        print(f'Ruta {state.src_ip} <-> {state.dst_ip} renovada.')

    # Elimina las reglas de flow_routing de ambos sentidos del tráfico en todos los switches,
    # borrando la ruta dinámica.
    def delete_bidirectional_route(self, key, state):
        reverse_path = list(reversed(state.path))

        self.delete_direction(state.src_ip, state.dst_ip, state.path)
        self.delete_direction(state.dst_ip, state.src_ip, reverse_path)

        del self.dynamic_routes[key]
        print(f'Ruta {state.src_ip} <-> {state.dst_ip} eliminada por inactividad.')


    # -------------------------------------------------------------------------
    # Gestión de digest
    # -------------------------------------------------------------------------
    
    # Procesa un digest NEW_FLOW recibido desde un switch.
    # Si el par de hosts es conocido y todavía no tiene ruta dinámica,
    # calcula el mejor camino e instala la ruta.
    def handle_new_flow(self, switch_id, src_ip, dst_ip):
        
        if is_management_traffic(src_ip, dst_ip):
            return
    
        # Comprobamos que ambos hosts son conocidos en la topología.
        if src_ip not in HOSTS or dst_ip not in HOSTS:
            print(f'Digest NEW_FLOW ignorado: host desconocido {src_ip} -> {dst_ip}')
            return

        key = pair_key(src_ip, dst_ip)
        if key in self.dynamic_routes:
            print(f'Digest NEW_FLOW ignorado: ya existe ruta para {src_ip} <-> {dst_ip}')
            return

        print(f"Nuevo par detectado en {SWITCHES[switch_id]['name']}: {src_ip} -> {dst_ip}")
        path = self.choose_path(src_ip, dst_ip)
        self.install_bidirectional_route(src_ip, dst_ip, path)

    # Procesa un digest FLOW_ALIVE recibido desde un switch.
    # Si la ruta asociada al par de hosts está en probation, 
    # la ruta se renueva y vuelve al estado ACTIVE.
    def handle_flow_alive(self, switch_id, src_ip, dst_ip):
        if is_management_traffic(src_ip, dst_ip):
            return
        
        key = pair_key(src_ip, dst_ip)
        state = self.dynamic_routes.get(key)

        if state is None:
            print(f'Digest FLOW_ALIVE ignorado: no hay estado para {src_ip} <-> {dst_ip}')
            return

        if state.status != 'PROBATION':
            print(f'Digest FLOW_ALIVE recibido para ruta ya activa {src_ip} <-> {dst_ip}')
            return

        print(f"FLOW_ALIVE recibido en {SWITCHES[switch_id]['name']}: {src_ip} -> {dst_ip}")
        self.renew_route(state)

    # Consulta todos los switches para leer los digest recibidos.
    # Según el tipo recibido, se gestiona como nuevo flujo o como confirmación 
    # de ruta activa durante probation.
    def poll_digests(self):
        for sw_id, controller in self.controllers.items():
            # Lo pones a 0.01, ya que 0 no tiene el comportamiento esperado.
            digest_list = controller.get_digest_list(timeout=0.01)
            if digest_list is None:
                continue

            for entry in digest_list.data:
                try:
                    digest_type, switch_id, src_ip, dst_ip = parse_flow_digest_entry(entry)
                except Exception as exc:
                    print(f"No se pudo parsear un digest de {SWITCHES[sw_id]['name']}: {exc}")
                    continue

                if digest_type == DIGEST_NEW_FLOW:
                    self.handle_new_flow(switch_id, src_ip, dst_ip)
                elif digest_type == DIGEST_FLOW_ALIVE:
                    self.handle_flow_alive(switch_id, src_ip, dst_ip)
                else:
                    print(f'Digest con tipo desconocido: {digest_type}')

    # -------------------------------------------------------------------------
    # Temporizadores de rutas
    # -------------------------------------------------------------------------

    # Revisa periódicamente los temporizadores de las rutas dinámicas.
    # Si una ruta activa supera su tiempo de vida, se pasa a probation.
    # Si una ruta en probation supera su ventana de prueba sin recibir tráfico,
    # se eliminan sus reglas dinámicas.
    def check_route_timers(self):
        now = time.monotonic()

        for key, state in list(self.dynamic_routes.items()):
            if state.status == 'ACTIVE' and now >= state.expires_at:
                self.enter_probation(state)

            elif state.status == 'PROBATION' and now >= state.probe_until:
                self.delete_bidirectional_route(key, state)

    # -------------------------------------------------------------------------
    # Bucle principal
    # -------------------------------------------------------------------------

    # Inicializa el controlador dinámico y deja el plano de control en ejecución.
    def run(self):
        # Conectamos el controlador con los switches.
        self.connect_switches()
        # Construimos el grafo de la topología NetworkX.
        self.build_graph()
        # Configuramos el estado estático inicial de los switches.
        self.reset_and_configure_static_state()
        # Habilitamos la recepción de digest.
        self.enable_digests()

        print('Plano de control configurado correctamente con routing dinámico habilitado.')

        # se consultan los digest y se revisan los temporizadores de las rutas dinámicas.
        try:
            while True:
                self.poll_digests()
                self.check_route_timers()
                time.sleep(0.05)
        except KeyboardInterrupt:
            print('\nApagando controlador dinámico...')
        # Cierra las conexiones con los switches al finalizar.
        finally:
            for controller in self.controllers.values():
                if hasattr(controller, 'teardown'):
                    controller.teardown()


if __name__ == '__main__':
    controller = DynamicTelemetryController()
    controller.run()