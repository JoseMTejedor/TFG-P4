/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;
// Ethernet Tipo Experimental reservado para hacer experimentos.
const bit<16> TYPE_CUSTOM = 0x88B6;
// Constante del identificador del protocolo UDP. 
const bit<8> PROTO_UDP = 17;
// Constante donde definimos el porcentaje de paquetes que se clonarán hacia la red de telemetría.
const bit<8> SAMPLE_PERCENT = 8w10;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

// Cabecera personalizada TMEA, para transportar las métricas entre switches.
// Esta cabecera viaja con el paquete original mientras está dentro de la red P4.
// Antes de entregar el paquete a un host, se elimina.
header measurement_t {
    bit<32> ingress_egress_time; // Tiempo desde el inicio del ingress hasta el inicio del egress.
    bit<32> queue_time; // Tiempo que el paquete ha pasado en la cola de salida.
    bit<32> accum_time; // Suma acumulada de los retardos ingress-egress.
    bit<48> prev_egress_t; //Timestamp del egress del anterior conmutador.
    bit<32> link_time; // Estimación del retardo entre switches. No fiable sin sincronización PTP.
    bit<8> prev_switch_id;  // Identificador del switch anterior.
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> length_;
    bit<16> checksum;
}

// Cabecera enviada dentro del paquete UDP clonado.
// Contiene los datos que se mandan al colector.
header telemetry_t{
    bit<8> switch_id;
    bit<8> prev_switch_id; 
    bit<32> ingress_egress_time;
    bit<32> queue_time;
    bit<32> accum_time;
    bit<32> link_time;
    bit<16> egress_port;
    bit<32> q_depth;
}

// Metadatos propios del programa.
// Los campos marcados con @field_list(1) se conservan al clonar el paquete.
// Se usan para pasar al clon los datos de telemetría antes de modificar o eliminar
// la cabecera measurement_t del paquete original. 
struct metadata {
    @field_list(1) bit<8> switch_id;
    @field_list(1) bit<8> prev_switch_id_backup;
    @field_list(1) bit<32> ingress_egress_time_backup;
    @field_list(1) bit<32> accum_time_backup;
    @field_list(1) bit<32> link_time_backup;
    @field_list(1) bit<32> queue_time_backup;
    @field_list(1) bit<16> egress_port_backup;
    @field_list(1) bit<32> q_depth_backup;
}

struct headers {
    ethernet_t   ethernet;
    measurement_t measurement;
    ipv4_t       ipv4;
    udp_t        udp; // Cabecera que solo se mandará en el clone.
    telemetry_t  telemetry; // Cabecera que solo se mandará en el clone.
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            TYPE_CUSTOM: parse_measurement;
            default: accept;
        }
    }

    state parse_measurement {
        packet.extract(hdr.measurement);
        transition parse_ipv4;
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);       
        transition accept;
    }


}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {
    action drop() {
        mark_to_drop(standard_metadata);
    }

    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
       
    } 

    // Acción para guardar el ID del switch en los metadatos.
    // Este valor se usa después en egress para identificar qué switch genera la muestra.
    action set_switch_id(bit<8> sw_id) {
        meta.switch_id = sw_id;
    }

    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = drop();
    }

    // Tabla que permite cargar el identificador del switch.
    // Al no tener key siempre se ejecuta default_action por defecto.
    // En vez de introducir table_add en el controlador, usaremos table_set_default,
    // para establecer set_switch_id como accion por defecto, con los datos del switch.
    table switch_info {
        actions = {
            set_switch_id;
            NoAction;
        }
        default_action = NoAction;
    }

    apply {

        // Cargamos el ID del switch nada más entrar al pipeline de ingress.
        switch_info.apply();

        if (hdr.ipv4.isValid()) {
            // Si el paquete todavía no lleva la cabecera de medición, la añadimos.
            // Esto ocurre en el primer switch P4 que procesa el paquete.
            if (!hdr.measurement.isValid()) {
                hdr.measurement.setValid();

                // Al activar una cabecera con setValid(), sus campos no quedan
                // inicializados automáticamente. Por eso se ponen a 0 para evitar
                // arrastrar datos basura.
                hdr.measurement.ingress_egress_time = 32w0;
                hdr.measurement.queue_time = 32w0;
                hdr.measurement.accum_time = 32w0;
                hdr.measurement.prev_egress_t = 48w0;
                hdr.measurement.link_time = 32w0;
                hdr.measurement.prev_switch_id = 8w0;

                // Cambiamos el EtherType para indicar que el paquete transporta
                // una cabecera personalizada antes de IPv4.
                hdr.ethernet.etherType = TYPE_CUSTOM;
            }
            
            // Aplicamos la tabla de forwarding IPv4.
            ipv4_lpm.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {

    action remove_header() {
        // Eliminamos la cabecera personalizada y restauramos el EtherType 
        // a IPv4 para que el host entienda el paquete.
        hdr.measurement.setInvalid();
        hdr.ethernet.etherType = TYPE_IPV4;       
    }

    table remove_header_tbl {
        key = {
            standard_metadata.egress_port: exact;
        }
        actions = {
            remove_header;
            NoAction;
        }
        default_action = NoAction;
    }

    // Acción para modificar la MAC e IP destino del paquete clonado.
    // El clon se redirige hacia el colector de telemetría.

    //  También se cambia la IP de origen. Al ser una red dedicada para la telemetría,
    //  el h_col no puede alcanzar los otros host, por lo que el sistema de seguridad de linux descartará
    //  el paquete. En consecuencia, cambiamos la IP origen por una dentro de la red dedicada.
    action route_telemetry(macAddr_t dst_mac, ip4Addr_t dst_ip, ip4Addr_t src_ip) {
        hdr.ethernet.dstAddr = dst_mac;
        hdr.ipv4.dstAddr = dst_ip;
        hdr.ipv4.srcAddr = src_ip;
    }

    // Tabla que nos permite introducir los datos de MAC e IP destino
    table telemetry_routing {
        actions = { 
            route_telemetry; 
            NoAction; 
        }
        default_action = NoAction;
    }

    apply { 

        //TRAFICO NORMAL
        // standard_metadata.instance_type indica el tipo de paquete.
        // En BMv2/v1model, el valor 0 corresponde a un paquete normal,
        // es decir, no es un clon.
        if (standard_metadata.instance_type == 0) {

            if (hdr.measurement.isValid()) {
                // Guardamos los timestamps locales del switch.
                bit<48> current_ingress = standard_metadata.ingress_global_timestamp;
                bit<48> current_egress = standard_metadata.egress_global_timestamp;

                // Calculamos el retardo desde el inicio de ingress hasta el inicio de egress.
                bit<32> delta = (bit<32>)(current_egress - current_ingress);
                hdr.measurement.ingress_egress_time = delta;

                // Tiempo que pasa el paquete dentro de la cola de salida.
                hdr.measurement.queue_time = standard_metadata.deq_timedelta;

                //Calculamos el Link Delay 
                // Se calcula como: ingress_timestamp_actual - egress_timestamp_anterior.
                // Si el dato de prev_egress es distinto de 0 (dato de inicialización) se hace el calculo

                // En esta implementación el valor no es fiable porque cada switch usa su propio reloj.
                // Al no estar sincronizados, pueden aparecer valores incoherentes o underflow.
                // Se mantiene el campo por interés experimental y porque sería válido en un entorno
                // con sincronización PTP.
                if (hdr.measurement.prev_egress_t > 0){
                    hdr.measurement.link_time = (bit<32>)(current_ingress - hdr.measurement.prev_egress_t);
                } else {
                    hdr.measurement.link_time = 32w0;
                }

                // Retardo acumulado total incluyendo link_time.
                // Actualmente no se usa porque link_time no es fiable.
                // En un entorno con PTP podría volver a utilizarse.
                // hdr.measurement.accum_time = hdr.measurement.accum_time + delta + hdr.measurement.link_time;

                // Retardo acumulado medible.
                // Solo se acumula el retardo ingress-egress local de cada switch.
                hdr.measurement.accum_time = hdr.measurement.accum_time + delta;

                //Sobreescribimos el prev_egress_t.
                hdr.measurement.prev_egress_t = current_egress;

                // MUESTREO ALEATORIO
                // Para no saturar la red de telemetría ni el colector, no se clonan todos
                // los paquetes. Se genera un número aleatorio entre 1 y 100 y solo se clona
                // el paquete si el valor cae dentro del porcentaje configurado.
                bit<8> rand_val;
                random<bit<8>>(rand_val, 8w1, 8w100);
                if(rand_val <= SAMPLE_PERCENT){
                    // Guardamos prev_switch_id antes de actualizarlo, para que el clon
                    // sepa de qué switch venía el paquete.
                    meta.prev_switch_id_backup = hdr.measurement.prev_switch_id;

                    // Guardamos en metadata los datos que debe conservar el clon.
                    // Se hace solo si el paquete se va a clonar, para evitar escrituras
                    // innecesarias en los paquetes que no se envían al colector.
                    meta.ingress_egress_time_backup = hdr.measurement.ingress_egress_time;
                    meta.queue_time_backup = hdr.measurement.queue_time;
                    meta.accum_time_backup = hdr.measurement.accum_time;
                    meta.link_time_backup = hdr.measurement.link_time;
                    meta.egress_port_backup = (bit<16>)standard_metadata.egress_port;
                    meta.q_depth_backup = (bit<32>)standard_metadata.deq_qdepth;
                
                    //Clonamos el paquete. Se usa clone_preserving_field_list() 
                    //para pasarle los metadatos al clone.
                    clone_preserving_field_list(CloneType.E2E, 500, 1);
                }
            
                // Actualizamos prev_switch_id para que el siguiente switch sepa
                // cuál fue el switch anterior.
                hdr.measurement.prev_switch_id = meta.switch_id;

                //Comprobamos si hay que quitar la cabecera (si vamos a un host).
                remove_header_tbl.apply();
            }
        } 
        
        // TRÁFICO CLONADO
        // standard_metadata.instance_type == 2 indica que es un paquete clonado
        // desde el egress. En este caso no se reenvía como tráfico normal,
        // sino que se transforma en un paquete UDP de telemetría hacia el colector.
        else if (standard_metadata.instance_type == 2){

            // Activamos UDP y telemetry para construir el paquete que se enviará al colector.
            hdr.measurement.setInvalid();
            hdr.udp.setValid();
            hdr.telemetry.setValid();

            // Rellenamos la cabecera telemetry.
            hdr.telemetry.switch_id = meta.switch_id;
            hdr.telemetry.prev_switch_id = meta.prev_switch_id_backup; 
            hdr.telemetry.ingress_egress_time = meta.ingress_egress_time_backup;
            hdr.telemetry.queue_time = meta.queue_time_backup;
            hdr.telemetry.accum_time = meta.accum_time_backup;
            hdr.telemetry.link_time = meta.link_time_backup;
            hdr.telemetry.egress_port = meta.egress_port_backup; 
            hdr.telemetry.q_depth = meta.q_depth_backup;

            //Modificamos el etherType por el de IP.
            hdr.ethernet.etherType = TYPE_IPV4; 
            // Indicar en el protocolo IP que se está usando UDP.
            hdr.ipv4.protocol = PROTO_UDP;
            // Tamaño del paquete IP sin contar la cabecera de ethernet.
            hdr.ipv4.totalLen = 52;

            // Aplicamos la tabla para que modifique los valores de MAC e IP destino
            // forzando los valores del colector.
            telemetry_routing.apply();

            hdr.udp.srcPort = 12345;
            // Puerto por el que llegará al colector.
            hdr.udp.dstPort = 8192; 
            // Longitud UDP: 8 UDP + 24 telemetry = 32 bytes.
            hdr.udp.length_ = 32;   
            // Establecemos checksum a 0 para que linux ignore la comprobación .
            hdr.udp.checksum = 0;   

            // Cortamos el paquete para mandar solo las cabeceras necesarias:
            // 14 Ethernet + 20 IPv4 + 8 UDP + 24 telemetry = 66 bytes.
            truncate(66);
        }   
    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers  hdr, inout metadata meta) {
     apply {
        update_checksum(
        hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.measurement);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.udp);
        packet.emit(hdr.telemetry);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
