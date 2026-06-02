import subprocess
import re
import statistics

# -----------------------------------------------------------------------------
# Parámetros del experimento
# -----------------------------------------------------------------------------

# IP de h4: host conectado al mismo switch que h1.
# Se usa como referencia sin enlaces entre switches.
IP_H4 = "10.0.1.2"

# IP de h5: host alcanzable desde h1 atravesando dos enlaces entre switches.
IP_H5 = "10.0.4.1"

# Pings de calentamiento para evitar efectos iniciales como ARP.
WARMUP_PINGS = 5

# Número de pings útiles por tanda.
PING_COUNT = 100

# Número de tandas para cada medida.
ROUNDS = 3

# Tiempo entre pings.
PING_INTERVAL = 0.2

# h1 -> h5 atraviesa 2 enlaces entre switches en la ida.
# Como el ping mide RTT, también incluye la vuelta:
#   2 enlaces ida + 2 enlaces vuelta = 4 cruces de enlace
NUM_LINK_CROSSES_RTT = 4


def run_ping(destination_ip, count):
    """
    Ejecuta ping hacia una IP y extrae el RTT medio que aparece en la salida.
    Devuelve el valor avg en milisegundos.
    """

    command = [
        "ping",
        "-c", str(count),
        "-i", str(PING_INTERVAL),
        destination_ip,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Error ejecutando ping a {destination_ip}:\n{result.stderr}"
        )

    output = result.stdout

    # Busca una línea del tipo:
    # rtt min/avg/max/mdev = 0.123/0.456/0.789/0.010 ms
    match = re.search(
        r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = "
        r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms",
        output,
    )

    if match is None:
        raise ValueError(
            f"No se pudo extraer el RTT medio de la salida de ping:\n{output}"
        )

    avg_rtt_ms = float(match.group(2))
    return avg_rtt_ms


def measure(name, destination_ip):
    """
    Realiza los pings de calentamiento y después varias tandas de medida.
    Devuelve una lista con los RTT medios de cada tanda.
    """

    print(f"\nMedida {name}: ping a {destination_ip}")

    print(f"  Calentamiento: {WARMUP_PINGS} pings")
    run_ping(destination_ip, WARMUP_PINGS)

    values = []

    for round_number in range(1, ROUNDS + 1):
        avg_rtt = run_ping(destination_ip, PING_COUNT)
        values.append(avg_rtt)
        print(f"  Tanda {round_number}: RTT medio = {avg_rtt:.6f} ms")

    return values


def main():
    print("Cálculo experimental de BASE_LINK_DELAY")
    print("---------------------------------------")

    rtt_h1_h4_values = measure("h1 -> h4", IP_H4)
    rtt_h1_h5_values = measure("h1 -> h5", IP_H5)

    rtt_h1_h4 = statistics.mean(rtt_h1_h4_values)
    rtt_h1_h5 = statistics.mean(rtt_h1_h5_values)

    diff_rtt = rtt_h1_h5 - rtt_h1_h4

    base_link_delay_ms = diff_rtt / NUM_LINK_CROSSES_RTT
    base_link_delay_us = base_link_delay_ms * 1000

    print("\nResumen")
    print("-------")
    print(f"RTT medio h1 -> h4: {rtt_h1_h4:.6f} ms")
    print(f"RTT medio h1 -> h5: {rtt_h1_h5:.6f} ms")
    print(f"Diferencia RTT:      {diff_rtt:.6f} ms")

    print("\nCálculo")
    print("-------")
    print(
        f"BASE_LINK_DELAY = ({rtt_h1_h5:.6f} - {rtt_h1_h4:.6f}) "
        f"/ {NUM_LINK_CROSSES_RTT}"
    )
    print(f"BASE_LINK_DELAY = {base_link_delay_ms:.6f} ms")
    print(f"BASE_LINK_DELAY = {base_link_delay_us:.2f} us")

    print("\nValor para poner en el controlador")
    print("----------------------------------")
    print(f"BASE_LINK_DELAY = {round(base_link_delay_us)}")


if __name__ == "__main__":
    main()