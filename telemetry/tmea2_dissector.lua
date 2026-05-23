-- 1. Declaramos nuestro protocolo TMEA. El primer valor es el identificador para el filtro 
local tmea2_proto = Proto("tmea2", "TMEA v2- Time Measurement Protocol")

-- 2. Definimos los campos de la cabecera
local f_ingress_egress_time = ProtoField.uint32("tmea2.ingress_egress_time", "Retardo ingress-egress", base.DEC)
local f_queue_time = ProtoField.uint32("tmea2.queue_egress_time", "Tiempo de cola", base.DEC)
local f_accum_time = ProtoField.uint32("tmea2.accum_time", "Retardo acumulado", base.DEC)
-- Para f_prev_egress_t que tiene 48 bits usamos uint64 que admite hasta 8 bytes
local f_prev_egress_t = ProtoField.uint64("tmea2.prev_egress_t", "Egress timestamp del conmutador anterior", base.DEC)
local f_link_time = ProtoField.uint32("tmea2.link_time", "Retardo del enlace estimado", base.DEC)
local f_prev_switch_id = ProtoField.uint8("tmea2.f_prev_switch_id", "ID del conmutador anterior", base.DEC)

-- Añadimos los campos creados a la cabecera
tmea2_proto.fields = { 
    f_ingress_egress_time,
    f_queue_time,
    f_accum_time,
    f_prev_egress_t,
    f_link_time,
    f_prev_switch_id
 }

-- 3. Función que lee los bytes
function tmea2_proto.dissector(buffer, pinfo, tree)
    
    -- La cabecera measurement_t ocupa 23 bytes:
    -- 4 ingress_egress_time
    -- 4 queue_time
    -- 4 accum_time
    -- 6 prev_egress_t
    -- 4 link_time
    -- 1 prev_switch_id
    if buffer:len() < 23 then return end

    pinfo.cols.protocol = "TMEAv2"

    local subtree = tree:add(tmea2_proto, buffer(0,23), "Cabecera TMEA v2")

    --Mapeo de los campos
    subtree:add(f_ingress_egress_time, buffer(0,4))
    subtree:add(f_queue_time, buffer(4,4))
    subtree:add(f_accum_time, buffer(8,4))
    subtree:add(f_prev_egress_t, buffer(12,6))
    subtree:add(f_link_time, buffer(18,4))
    subtree:add(f_prev_switch_id, buffer(22,1))

    -- Después de measurement_t empieza la cabecera IPv4 original
    local ipv4_dissector = Dissector.get("ip")
    ipv4_dissector:call(buffer(23):tvb(), pinfo, tree)
end

-- 4. Registramos el protocolo en el EtherType (0x88B6)
local eth_table = DissectorTable.get("ethertype")
eth_table:add(0x88B6, tmea2_proto)
