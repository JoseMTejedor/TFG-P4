/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;
// Se ha cambiado por un tipo ethernet tipo experimental reservado
const bit<16> TYPE_CUSTOM = 0x88B5;

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

// Cabecera personalizada para medir el tiempo que pasa el paquete desde que entra en el ingress hasta que llega al egress
header measurement_t {
    bit<32> in_time;
    bit<32> accum_time; // Campo para el retardo acumulado
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

struct metadata {
    /* empty */
}

struct headers {
    ethernet_t   ethernet;
    measurement_t measurement;
    ipv4_t       ipv4;
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

    apply {
        if (hdr.ipv4.isValid()) {
            
            // Si el paquete no tiene la cabecera la creamos
            if (!hdr.measurement.isValid()) {
                hdr.measurement.setValid();
                // Inicializa el valor en 0. Al reservar memoria con setValid, el switch no la limpia
                // por lo que podemos arrastrar datos "basura" de paquetes anteriores. Por eso lo ponemos a 0
                hdr.measurement.in_time = 32w0;
                // Inicializa el valor del tiempo acumulado a 0
                hdr.measurement.accum_time = 32w0;

                // Cambiamos el EtherType para indicar que ahora llevamos una cabecera personalizada 
                hdr.ethernet.etherType = TYPE_CUSTOM;
            }
            
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
        // Eliminamos la cabecera personlizad y restauramos el EtherType a IPv4 para que el host entienda el paquete
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

    apply { 

        if (hdr.measurement.isValid()) {
            //Calculamos el tiempo de residencia local
            bit<32> delta = (bit<32>)(standard_metadata.egress_global_timestamp - standard_metadata.ingress_global_timestamp);
            hdr.measurement.in_time = delta;

            //Añadimos el tiempo de retardo actual al tiempo total acumulado en el paquete
            hdr.measurement.accum_time = hdr.measurement.accum_time + delta;

            //Comprobamos si hay que quitar la cabecera (si vamos a un host)
            remove_header_tbl.apply();
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
