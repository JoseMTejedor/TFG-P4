-- 1. Declaramos nuestro protocolo TMEA. El primer valor es el identificador para el filtro 
-- wireshark. El segundo valor es el nombre de visualizacion del protocolo.
-- La variable tmea_proto para añadirle los campos a nuestro protocolo.
local tmea_proto = Proto("tmea", "TMEA - Time Measurement Protocol")

-- 2. Definimos los campos de la cabecera
-- ProtoField.uint32: indiciamos que el campo tiene un tamaño de 32 bits
-- Primer valor es el identificador para el filtro
-- Segundo valor es el texto descriptivo de la cabecera
-- base.DEC: Representacion numérica de la cabecera
local f_in_time = ProtoField.uint32("tmea.in_time", "Tiempo de residencia local en el conmutador", base.DEC)
local f_accum_time = ProtoField.uint32("tmea.accum_time", "Retardo acumulado", base.DEC)

-- Añadimos los campos creados a la cabecera
tmea_proto.fields = { f_in_time, f_accum_time }

-- 3. Función que lee los bytes
-- Wireshark entrega tres argumentos a nuestra funcion
-- buffer: Son los datos crudos, los bytes del paquete
-- pinfo: Permite modificar las columnas de la vista de Wireshark
-- tree: Representa la ventana central donde desplegamos los detalles de cada paquete
function tmea_proto.dissector(buffer, pinfo, tree)
    
    --Para ignorar paquetes mas pequeños que nuestra cabecera. 
    --Proteccion frente a paquetes corruptos
    if buffer:len() < 8 then return end

    --Cambiamos el nombre en la columna "Protocol" de Wireshark por el nombre de nuestro protocolo
    pinfo.cols.protocol = "TMEA"

    --Seccion desplegable principal
    local subtree = tree:add(tmea_proto, buffer(0,8), "Cabecera TMEA")

    --Añadimos los campos indicando los bytes que ocupa cada uno
    -- El primer dato es la definicion del campo de la cabecera
    -- El segundo dato, son los bytes del campo.
    -- El primer valor es donde empieza, y el segundo cuantos bytes ocupa
    subtree:add(f_in_time,buffer(0,4))
    subtree:add(f_accum_time,buffer(4,4))

    -- Le pasamos el control al decodificador IPv4 paraa el resto del paquete
    -- Primero llamamos al decodificador oficiaal de IP
    -- Segundo le damos el resto del paquete, sin los 8 bytes que hemos leido
    local ipv4_dissector = Dissector.get("ip")
    ipv4_dissector:call(buffer(8):tvb(), pinfo, tree)
end

-- 4. Registramos el protocolo en el EtherType (0x88B5)
-- Guardamos en eth_table la tabla de Wireshark donde decide que hacer con cada paquete ethernet
-- La segunda instruccion le dice que cada vez que le llegue el type 0x88B5 use mi protocolo
local eth_table = DissectorTable.get("ethertype")
eth_table:add(0x88B5, tmea_proto)
