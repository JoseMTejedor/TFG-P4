-- 1. Declaramos nuestro protocolo TMEA. El primer valor es el identificador para el filtro 
local tmea2_proto = Proto("tmea2", "TMEA v2- Time Measurement Protocol")

-- 2. Definimos los campos de la cabecera
local f_in_time = ProtoField.uint32("tmea2.in_time", "Tiempo de residencia local en el conmutador", base.DEC)
local f_accum_time = ProtoField.uint32("tmea2.accum_time", "Retardo acumulado", base.DEC)
-- Añadimos los dos campos nuevos
-- Para f_prev_egress_t que tiene 48 bits usamos uint64 que admite hasta 8 bytes
local f_prev_egress_t = ProtoField.uint64("tmea2.prev_egress_t", "Egress Timestamp del anterior conmutador", base.DEC)
local f_link_time = ProtoField.uint32("tmea2.link_time", "Tiempo de retrado entre el egress anterior y el ingress actual", base.DEC)

-- Añadimos los campos creados a la cabecera
tmea2_proto.fields = { f_in_time, f_accum_time, f_prev_egress_t, f_link_time }

-- 3. Función que lee los bytes
function tmea2_proto.dissector(buffer, pinfo, tree)
    
    --Comprobamos que el paquete tenga la menos 18 bytes
    if buffer:len() < 18 then return end

    pinfo.cols.protocol = "TMEAv2"

    local subtree = tree:add(tmea2_proto, buffer(0,18), "Cabecera TMEA v2")

    --Mapeo de los campos
    subtree:add(f_in_time, buffer(0,4))
    subtree:add(f_accum_time, buffer(4,4))
    subtree:add(f_prev_egress_t, buffer(8,6))
    subtree:add(f_link_time, buffer(14,4))


    local ipv4_dissector = Dissector.get("ip")
    ipv4_dissector:call(buffer(18):tvb(), pinfo, tree)
end

-- 4. Registramos el protocolo en el EtherType (0x88B6)
local eth_table = DissectorTable.get("ethertype")
eth_table:add(0x88B6, tmea2_proto)
