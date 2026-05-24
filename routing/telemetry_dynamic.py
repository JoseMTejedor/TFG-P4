import time
import sqlite3
import ipaddress
from dataclasses import dataclass

import networkx as nx
from p4utils.utils.sswitch_p4runtime_API import SimpleSwitchP4RuntimeAPI


# -----------------------------------------------------------------------------
# Parámetros generales del controlador
# -----------------------------------------------------------------------------

P4RT_PATH = 'telemetry_p4rt.txt'
JSON_PATH = 'telemetry.json'
DB_FILE = 'telemetry.db'

# Coste base asumido por enlace entre switches.
# De momento usamos 1 ms = 1000 us. Más adelante se puede sustituir por el
# valor estimado a partir de las medidas RTT.
BASE_LINK_DELAY_US = 1000

# Número de muestras usadas por puerto para calcular la media amortiguada.
# Si para un puerto solo hay 5 muestras y N=30, se divide entre 30 igualmente.
# Esto equivale a rellenar con ceros las muestras que faltan y evita
# sobrerreaccionar cuando hay pocos datos.
SAMPLES_PER_PORT = 30

# Número máximo de filas recientes que se leen de la base de datos para calcular
# las medias por puerto. No afecta al cálculo final salvo que haya muchísimas
# muestras recientes.
DB_READ_LIMIT = 3000

# Umbrales para seleccionar una ruta alternativa.
# La ruta alternativa solo se elige si mejora a la ruta por defecto de forma
# clara en términos absolutos y relativos.
REL_THRESHOLD = 0.20
ABS_THRESHOLD_US = BASE_LINK_DELAY_US

# Umbral auxiliar de congestión. Solo se plantea desviar tráfico si la ruta por
# defecto tiene al menos este valor de cola media en alguno de sus puertos.
QUEUE_CONGESTION_US = 1000

# Gestión de vida de las rutas dinámicas.
ROUTE_TTL = 60
PROBATION_WINDOW = 15

# Tipos de digest definidos en P4.
DIGEST_NEW_FLOW = 1
DIGEST_FLOW_ALIVE = 2


# -----------------------------------------------------------------------------
# Información fija de switches, hosts y enlaces
# -----------------------------------------------------------------------------

SWITCHES = {
    1: {'name': 'sA', 'grpc_port': 9559, 'collector_src_ip': '10.99.0.1'},
    2: {'name': 'sB', 'grpc_port': 9560, 'collector_src_ip': '10.99.0.2'},
    3: {'name': 'sC', 'grpc_port': 9561, 'collector_src_ip': '10.99.0.3'},
    4: {'name': 'sD', 'grpc_port': 9562, 'collector_src_ip': '10.99.0.4'},
    5: {'name': 'sE', 'grpc_port': 9563, 'collector_src_ip': '10.99.0.5'},
    6: {'name': 'sF', 'grpc_port': 9564, 'collector_src_ip': '10.99.0.6'},
    7: {'name': 'sG', 'grpc_port': 9565, 'collector_src_ip': '10.99.0.7'},
}

# Hosts finales. La IP se guarda como texto para instalar reglas de tabla, y el
# controlador la convierte a entero cuando necesita compararla con la base de datos.
HOSTS = {
    '10.0.1.1': {'name': 'h1', 'switch': 1, 'port': 1, 'mac': '00:00:00:00:00:01'},
    '10.0.1.2': {'name': 'h4', 'switch': 1, 'port': 6, 'mac': '00:00:00:00:00:04'},
    '10.0.3.1': {'name': 'h2', 'switch': 3, 'port': 1, 'mac': '00:00:00:00:00:02'},
    '10.0.4.1': {'name': 'h5', 'switch': 4, 'port': 1, 'mac': '00:00:00:00:00:05'},
    '10.0.4.2': {'name': 'h6', 'switch': 4, 'port': 6, 'mac': '00:00:00:00:00:06'},
    '10.0.5.1': {'name': 'h3', 'switch': 5, 'port': 1, 'mac': '00:00:00:00:00:03'},
}

# Enlaces entre switches. Cada entrada indica cómo salir desde un switch hacia
# su vecino: puerto de salida y MAC del siguiente salto.
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


@dataclass
class FlowState:
    src_ip: str
    dst_ip: str
    path: list
    status: str
    expires_at: float
    probe_until: float = 0.0


# -----------------------------------------------------------------------------
# Funciones auxiliares
# -----------------------------------------------------------------------------

def ip_to_int(ip_str):
    return int(ipaddress.IPv4Address(ip_str))


def int_to_ip(ip_int):
    return str(ipaddress.IPv4Address(ip_int))


def pair_key(src_ip, dst_ip):
    """Devuelve una clave no direccional para tratar h1-h6 y h6-h1 igual."""
    return tuple(sorted([ip_to_int(src_ip), ip_to_int(dst_ip)]))


def p4data_bitstring_to_int(p4data):
    """Convierte un campo bit<W> recibido en un digest a entero Python."""
    return int.from_bytes(p4data.bitstring, byteorder='big')


def parse_flow_digest_entry(entry):
    """
    Extrae los campos del digest flow_digest_t.

    Orden esperado en P4:
        digest_type, switch_id, src_ip, dst_ip
    """
    # En P4Runtime, el digest de un struct llega como P4Data.struct.members.
    struct_data = getattr(entry, 'struct')
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
        self.controllers = {}
        self.graph = nx.Graph()
        self.flows = {}

    # -------------------------------------------------------------------------
    # Inicialización
    # -------------------------------------------------------------------------

    def connect_switches(self):
        for sw_id, info in SWITCHES.items():
            self.controllers[sw_id] = SimpleSwitchP4RuntimeAPI(
                device_id=sw_id,
                grpc_port=info['grpc_port'],
                p4rt_path=P4RT_PATH,
                json_path=JSON_PATH,
            )

    def reset_and_configure_static_state(self):
        for sw_id, controller in self.controllers.items():
            controller.reset_state()
            controller.table_set_default('switch_info', 'set_switch_id', [str(sw_id)])
            controller.table_set_default(
                'telemetry_routing',
                'route_telemetry',
                ['00:00:00:99:99:99', '10.99.0.100', SWITCHES[sw_id]['collector_src_ip']],
            )
            controller.cs_create(500, [5])
            controller.table_set_default('ipv4_lpm', 'drop')

        self.install_static_ipv4_routes()
        self.install_remove_header_rules()

    def enable_digests(self):
        for sw_id, controller in self.controllers.items():
            # El nombre del digest es el nombre del struct usado en P4:
            # digest<flow_digest_t>(1, {...})
            controller.digest_enable(
                'flow_digest_t',
                max_timeout_ns=0,
                max_list_size=1,
                ack_timeout_ns=0,
            )
            print(f'Digest flow_digest_t habilitado en s{sw_id}')

    def build_graph(self):
        for sw_id in SWITCHES:
            self.graph.add_node(sw_id)

        for src_sw, neighbors in LINKS.items():
            for dst_sw in neighbors:
                if not self.graph.has_edge(src_sw, dst_sw):
                    self.graph.add_edge(src_sw, dst_sw, base_cost=BASE_LINK_DELAY_US)

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

    def install_remove_header_rules(self):
        # Puertos conectados a hosts finales. En esos puertos se elimina la
        # cabecera measurement_t antes de entregar el paquete al host.
        self.controllers[1].table_add('remove_header_tbl', 'remove_header', ['1'])
        self.controllers[1].table_add('remove_header_tbl', 'remove_header', ['6'])
        self.controllers[3].table_add('remove_header_tbl', 'remove_header', ['1'])
        self.controllers[4].table_add('remove_header_tbl', 'remove_header', ['1'])
        self.controllers[4].table_add('remove_header_tbl', 'remove_header', ['6'])
        self.controllers[5].table_add('remove_header_tbl', 'remove_header', ['1'])

    # -------------------------------------------------------------------------
    # Métricas desde la base de datos
    # -------------------------------------------------------------------------

    def read_port_metrics(self, exclude_pair_key=None):
        """
        Devuelve medias amortiguadas por (switch_id, egress_port).

        Para cada puerto se usan como máximo SAMPLES_PER_PORT muestras. Si hay
        menos, se divide igualmente entre SAMPLES_PER_PORT, equivalente a rellenar
        con ceros. Si exclude_pair_key se pasa, se ignoran muestras de ese par en
        ambos sentidos para evitar autointerferencia directa.
        """
        samples = {}

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT switch_id, egress_port, ingress_egress_time, queue_time, src_ip, dst_ip
                FROM link_metrics
                ORDER BY id DESC
                LIMIT ?
            ''', (DB_READ_LIMIT,))
            rows = cursor.fetchall()
            conn.close()
        except sqlite3.Error:
            return {}

        for sw_id, port, ingress_egress_time, queue_time, src_ip, dst_ip in rows:
            if exclude_pair_key is not None and tuple(sorted([src_ip, dst_ip])) == exclude_pair_key:
                continue

            key = (sw_id, port)
            if key not in samples:
                samples[key] = []

            if len(samples[key]) < SAMPLES_PER_PORT:
                samples[key].append((ingress_egress_time, queue_time))

        metrics = {}
        for key, values in samples.items():
            avg_ingress_egress = sum(v[0] for v in values) / SAMPLES_PER_PORT
            avg_queue = sum(v[1] for v in values) / SAMPLES_PER_PORT
            metrics[key] = {
                'avg_ingress_egress_time': avg_ingress_egress,
                'avg_queue_time': avg_queue,
                'num_samples': len(values),
            }

        return metrics

    # -------------------------------------------------------------------------
    # Cálculo de rutas
    # -------------------------------------------------------------------------

    def edge_cost(self, src_sw, dst_sw, metrics):
        out_port = LINKS[src_sw][dst_sw]['port']
        port_metrics = metrics.get((src_sw, out_port), {})
        avg_ingress_egress = port_metrics.get('avg_ingress_egress_time', 0)
        return BASE_LINK_DELAY_US + avg_ingress_egress

    def path_cost(self, path, metrics):
        if len(path) <= 1:
            return 0

        cost = 0
        for src_sw, dst_sw in zip(path[:-1], path[1:]):
            cost += self.edge_cost(src_sw, dst_sw, metrics)
        return cost

    def max_queue_on_path(self, path, metrics):
        max_queue = 0
        for src_sw, dst_sw in zip(path[:-1], path[1:]):
            out_port = LINKS[src_sw][dst_sw]['port']
            port_metrics = metrics.get((src_sw, out_port), {})
            max_queue = max(max_queue, port_metrics.get('avg_queue_time', 0))
        return max_queue

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

        # Actualizamos pesos dinámicos temporalmente para calcular el mejor camino.
        for u, v in self.graph.edges():
            forward_cost = self.edge_cost(u, v, metrics)
            reverse_cost = self.edge_cost(v, u, metrics)
            # El grafo es no dirigido. Para evitar complicar con DiGraph, usamos
            # el peor de ambos sentidos como coste conservador del enlace.
            self.graph[u][v]['dynamic_cost'] = max(forward_cost, reverse_cost)

        best_path = nx.shortest_path(self.graph, src_sw, dst_sw, weight='dynamic_cost')
        best_cost = self.path_cost(best_path, metrics)

        improvement_abs = default_cost - best_cost
        improvement_rel = improvement_abs / default_cost if default_cost > 0 else 0
        default_congested = default_max_queue >= QUEUE_CONGESTION_US

        print(
            f'Ruta por defecto {default_path}: coste={default_cost:.1f} us, '
            f'max_queue={default_max_queue:.1f} us'
        )
        print(
            f'Mejor ruta dinámica {best_path}: coste={best_cost:.1f} us, '
            f'mejora={improvement_abs:.1f} us ({improvement_rel:.1%})'
        )

        if (
            default_congested
            and improvement_abs >= ABS_THRESHOLD_US
            and improvement_rel >= REL_THRESHOLD
        ):
            print('Se selecciona la ruta dinámica alternativa.')
            return best_path

        print('Se mantiene la ruta por defecto/corta.')
        return default_path

    # -------------------------------------------------------------------------
    # Instalación, modificación y borrado de rutas dinámicas
    # -------------------------------------------------------------------------

    def action_params_for_step(self, dst_ip, path, index):
        current_sw = path[index]

        if index == len(path) - 1:
            # Último switch del camino: reenviar al host destino.
            return HOSTS[dst_ip]['mac'], HOSTS[dst_ip]['port']

        next_sw = path[index + 1]
        link_info = LINKS[current_sw][next_sw]
        return link_info['mac'], link_info['port']

    def install_direction(self, src_ip, dst_ip, path, action_name='ipv4_forward'):
        for index, sw_id in enumerate(path):
            dst_mac, out_port = self.action_params_for_step(dst_ip, path, index)
            self.controllers[sw_id].table_add(
                'flow_routing',
                action_name,
                [src_ip, dst_ip],
                [dst_mac, str(out_port)],
            )

    def delete_direction(self, src_ip, dst_ip, path):
        for sw_id in path:
            self.controllers[sw_id].table_delete_match(
                'flow_routing',
                [src_ip, dst_ip],
            )

    def modify_ingress_action(self, src_ip, dst_ip, path, action_name):
        ingress_sw = path[0]
        dst_mac, out_port = self.action_params_for_step(dst_ip, path, 0)
        self.controllers[ingress_sw].table_modify_match(
            'flow_routing',
            action_name,
            [src_ip, dst_ip],
            [dst_mac, str(out_port)],
        )

    def install_bidirectional_route(self, src_ip, dst_ip, path):
        reverse_path = list(reversed(path))

        self.install_direction(src_ip, dst_ip, path, 'ipv4_forward')
        self.install_direction(dst_ip, src_ip, reverse_path, 'ipv4_forward')

        key = pair_key(src_ip, dst_ip)
        self.flows[key] = FlowState(
            src_ip=src_ip,
            dst_ip=dst_ip,
            path=path,
            status='ACTIVE',
            expires_at=time.monotonic() + ROUTE_TTL,
        )

        print(f'Ruta dinámica instalada para {src_ip} <-> {dst_ip}: {path}')

    def enter_probation(self, key, state):
        reverse_path = list(reversed(state.path))

        # Solo modificamos los switches de entrada de cada sentido. El resto de
        # reglas siguen reenviando normal.
        self.modify_ingress_action(state.src_ip, state.dst_ip, state.path, 'ipv4_forward_probe')
        self.modify_ingress_action(state.dst_ip, state.src_ip, reverse_path, 'ipv4_forward_probe')

        state.status = 'PROBATION'
        state.probe_until = time.monotonic() + PROBATION_WINDOW

        print(f'Ruta {state.src_ip} <-> {state.dst_ip} en probation.')

    def renew_route(self, key, state):
        reverse_path = list(reversed(state.path))

        self.modify_ingress_action(state.src_ip, state.dst_ip, state.path, 'ipv4_forward')
        self.modify_ingress_action(state.dst_ip, state.src_ip, reverse_path, 'ipv4_forward')

        state.status = 'ACTIVE'
        state.expires_at = time.monotonic() + ROUTE_TTL
        state.probe_until = 0.0

        print(f'Ruta {state.src_ip} <-> {state.dst_ip} renovada.')

    def delete_bidirectional_route(self, key, state):
        reverse_path = list(reversed(state.path))

        self.delete_direction(state.src_ip, state.dst_ip, state.path)
        self.delete_direction(state.dst_ip, state.src_ip, reverse_path)

        del self.flows[key]
        print(f'Ruta {state.src_ip} <-> {state.dst_ip} eliminada por inactividad.')

    # -------------------------------------------------------------------------
    # Gestión de digest
    # -------------------------------------------------------------------------

    def handle_new_flow(self, switch_id, src_ip, dst_ip):
        if src_ip not in HOSTS or dst_ip not in HOSTS:
            print(f'Digest NEW_FLOW ignorado: host desconocido {src_ip} -> {dst_ip}')
            return

        key = pair_key(src_ip, dst_ip)
        if key in self.flows:
            print(f'Digest NEW_FLOW ignorado: ya existe ruta para {src_ip} <-> {dst_ip}')
            return

        print(f'Nuevo par detectado en s{switch_id}: {src_ip} -> {dst_ip}')
        path = self.choose_path(src_ip, dst_ip)
        self.install_bidirectional_route(src_ip, dst_ip, path)

    def handle_flow_alive(self, switch_id, src_ip, dst_ip):
        key = pair_key(src_ip, dst_ip)
        state = self.flows.get(key)

        if state is None:
            print(f'Digest FLOW_ALIVE ignorado: no hay estado para {src_ip} <-> {dst_ip}')
            return

        if state.status != 'PROBATION':
            print(f'Digest FLOW_ALIVE recibido para ruta ya activa {src_ip} <-> {dst_ip}')
            return

        print(f'FLOW_ALIVE recibido en s{switch_id}: {src_ip} -> {dst_ip}')
        self.renew_route(key, state)

    def poll_digests(self):
        for sw_id, controller in self.controllers.items():
            digest_list = controller.get_digest_list(timeout=0)
            if digest_list is None:
                continue

            for entry in digest_list.data:
                try:
                    digest_type, switch_id, src_ip, dst_ip = parse_flow_digest_entry(entry)
                except Exception as exc:
                    print(f'No se pudo parsear un digest de s{sw_id}: {exc}')
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

    def check_route_timers(self):
        now = time.monotonic()

        for key, state in list(self.flows.items()):
            if state.status == 'ACTIVE' and now >= state.expires_at:
                self.enter_probation(key, state)

            elif state.status == 'PROBATION' and now >= state.probe_until:
                self.delete_bidirectional_route(key, state)

    # -------------------------------------------------------------------------
    # Bucle principal
    # -------------------------------------------------------------------------

    def run(self):
        self.connect_switches()
        self.build_graph()
        self.reset_and_configure_static_state()
        self.enable_digests()

        print('Plano de control configurado correctamente con routing dinámico habilitado.')

        try:
            while True:
                self.poll_digests()
                self.check_route_timers()
                time.sleep(0.05)
        except KeyboardInterrupt:
            print('\nApagando controlador dinámico...')
        finally:
            for controller in self.controllers.values():
                controller.teardown()


if __name__ == '__main__':
    controller = DynamicTelemetryController()
    controller.run()
