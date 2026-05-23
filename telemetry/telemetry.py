from p4utils.utils.sswitch_p4runtime_API import SimpleSwitchP4RuntimeAPI

# Switch A
controller = SimpleSwitchP4RuntimeAPI(device_id=1, grpc_port=9559,
                                      p4rt_path='telemetry_p4rt.txt',
                                      json_path='telemetry.json')

controller.reset_state()

#Cambiamos la accion por defecto de la tabla switch_info para añadir el ID del switch.
controller.table_set_default('switch_info','set_switch_id', ['1'])
#Cambiamos la accion por defecto de la tabla telemetry_routing para añadir la MAC y la IP de la base de datos.
controller.table_set_default('telemetry_routing', 'route_telemetry', ['00:00:00:99:99:99', '10.99.0.100', '10.99.0.1'])
#Indicamos que los mensajes clonados, con ID 500, se manden por el puerto 5.
controller.cs_create(500, [5])

#Reglas de enrutmiento estático.
controller.table_set_default('ipv4_lpm','drop')
# Rutas hacia los host locales
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.1.1/32'], ['00:00:00:00:00:01','1']) #h1
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.1.2/32'], ['00:00:00:00:00:04','6']) #h4
# Rutas Next-Hop, hacia otras subredes
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0A:0B', '2'])
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0A:07', '4'])
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0A:0F', '3'])

#Entradad para indicar que va hacia un host, por lo que quitamos la cabecera personalizada
#para que el sistema final pueda leer el paquete.
controller.table_add('remove_header_tbl', 'remove_header', ['1'])
controller.table_add('remove_header_tbl', 'remove_header', ['6'])

# Switch B
controller = SimpleSwitchP4RuntimeAPI(device_id=2, grpc_port=9560,
                                      p4rt_path='telemetry_p4rt.txt',
                                      json_path='telemetry.json')

controller.reset_state()

#Cambiamos la accion por defecto de la tabla switch_info para añadir el ID del switch.
controller.table_set_default('switch_info','set_switch_id', ['2'])
#Cambiamos la accion por defecto de la tabla telemetry_routing para añadir la MAC y la IP de la base de datos.
controller.table_set_default('telemetry_routing', 'route_telemetry', ['00:00:00:99:99:99', '10.99.0.100', '10.99.0.2'])
#Indicamos que los mensajes clonados, con ID 500, se manden por el puerto 5.
controller.cs_create(500, [5])

#Reglas de enrutmiento estático
controller.table_set_default('ipv4_lpm','drop')
# Rutas Next-Hop
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0B:0A', '3'])
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0B:0C', '2']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0B:0C', '2']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0B:0A', '3']) 


# Swicth C
controller = SimpleSwitchP4RuntimeAPI(device_id=3, grpc_port=9561,
                                      p4rt_path='telemetry_p4rt.txt',
                                      json_path='telemetry.json')

controller.reset_state()

#Cambiamos la accion por defecto de la tabla switch_info para añadir el ID del switch.
controller.table_set_default('switch_info','set_switch_id', ['3'])
#Cambiamos la accion por defecto de la tabla telemetry_routing para añadir la MAC y la IP de la base de datos.
controller.table_set_default('telemetry_routing', 'route_telemetry', ['00:00:00:99:99:99', '10.99.0.100', '10.99.0.3'])
#Indicamos que los mensajes clonados, con ID 500, se manden por el puerto 5.
controller.cs_create(500, [5])

#Reglas de enrutmiento estático 
controller.table_set_default('ipv4_lpm','drop')
# Rutas hacia los host locales
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.3.1/32'], ['00:00:00:00:00:02','1']) #h2
# Rutas Next-Hop, hacia otras subredes
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0C:0B', '3']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0C:0D', '2']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0C:0D', '2']) 

#Entradad para indicar que va hacia un host, por lo que quitamos la cabecera personalizada
#para que el sistema final pueda leer el paquete.
controller.table_add('remove_header_tbl', 'remove_header', ['1'])


# Swicth D
controller = SimpleSwitchP4RuntimeAPI(device_id=4, grpc_port=9562,
                                      p4rt_path='telemetry_p4rt.txt',
                                      json_path='telemetry.json')

controller.reset_state()

#Cambiamos la accion por defecto de la tabla switch_info para añadir el ID del switch.
controller.table_set_default('switch_info','set_switch_id', ['4'])
#Cambiamos la accion por defecto de la tabla telemetry_routing para añadir la MAC y la IP de la base de datos.
controller.table_set_default('telemetry_routing', 'route_telemetry', ['00:00:00:99:99:99', '10.99.0.100', '10.99.0.4'])
#Indicamos que los mensajes clonados, con ID 500, se manden por el puerto 5.
controller.cs_create(500, [5])

#Reglas de enrutmiento estático 
controller.table_set_default('ipv4_lpm','drop')
# Rutas hacia los host locales
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.1/32'], ['00:00:00:00:00:05', '1']) # h5
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.2/32'], ['00:00:00:00:00:06', '6']) # h6
# Rutas Next-Hop, hacia otras subredes
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0D:07', '4']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0D:0C', '3']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0D:0E', '2'])

#Entradad para indicar que va hacia un host, por lo que quitamos la cabecera personalizada
#para que el sistema final pueda leer el paquete.
controller.table_add('remove_header_tbl', 'remove_header', ['1'])
controller.table_add('remove_header_tbl', 'remove_header', ['6'])

# Swicth E
controller = SimpleSwitchP4RuntimeAPI(device_id=5, grpc_port=9563,
                                      p4rt_path='telemetry_p4rt.txt',
                                      json_path='telemetry.json')

controller.reset_state()

#Cambiamos la accion por defecto de la tabla switch_info para añadir el ID del switch.
controller.table_set_default('switch_info','set_switch_id', ['5'])
#Cambiamos la accion por defecto de la tabla telemetry_routing para añadir la MAC y la IP de la base de datos.
controller.table_set_default('telemetry_routing', 'route_telemetry', ['00:00:00:99:99:99', '10.99.0.100', '10.99.0.5'])
#Indicamos que los mensajes clonados, con ID 500, se manden por el puerto 5.
controller.cs_create(500, [5])

#Reglas de enrutmiento estático 
controller.table_set_default('ipv4_lpm','drop')
# Rutas hacia los host locales
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.1/32'], ['00:00:00:00:00:03', '1']) #h3
# Rutas Next-Hop, hacia otras subredes
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0E:0D', '3']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0E:0D', '3']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0E:0F', '2']) 

#Entradad para indicar que va hacia un host, por lo que quitamos la cabecera personalizada
#para que el sistema final pueda leer el paquete.
controller.table_add('remove_header_tbl', 'remove_header', ['1'])

# Switch F
controller = SimpleSwitchP4RuntimeAPI(device_id=6, grpc_port=9564,
                                      p4rt_path='telemetry_p4rt.txt',
                                      json_path='telemetry.json')

controller.reset_state()

#Cambiamos la accion por defecto de la tabla switch_info para añadir el ID del switch.
controller.table_set_default('switch_info','set_switch_id', ['6'])
#Cambiamos la accion por defecto de la tabla telemetry_routing para añadir la MAC y la IP de la base de datos.
controller.table_set_default('telemetry_routing', 'route_telemetry', ['00:00:00:99:99:99', '10.99.0.100', '10.99.0.6'])
#Indicamos que los mensajes clonados, con ID 500, se manden por el puerto 5.
controller.cs_create(500, [5])

#Reglas de enrutmiento estático 
controller.table_set_default('ipv4_lpm','drop')
# Rutas Next-Hop
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:0F:0A', '2'])
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:0F:0A', '2'])
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:0F:0E', '3']) 
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:0F:0E', '3']) 

# Switch G
controller = SimpleSwitchP4RuntimeAPI(device_id=7, grpc_port=9565,
                                      p4rt_path='telemetry_p4rt.txt',
                                      json_path='telemetry.json')

controller.reset_state()

#Cambiamos la accion por defecto de la tabla switch_info para añadir el ID del switch.
controller.table_set_default('switch_info','set_switch_id', ['7'])
#Cambiamos la accion por defecto de la tabla telemetry_routing para añadir la MAC y la IP de la base de datos.
controller.table_set_default('telemetry_routing', 'route_telemetry', ['00:00:00:99:99:99', '10.99.0.100', '10.99.0.7'])
#Indicamos que los mensajes clonados, con ID 500, se manden por el puerto 5.
controller.cs_create(500, [5])

#Reglas de enrutmiento estático 
controller.table_set_default('ipv4_lpm','drop')
# Rutas Next-Hop
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:00:00:00:07:0A', '2'])
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.3.0/24'], ['00:00:00:00:07:0A', '2'])
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.4.0/24'], ['00:00:00:00:07:0D', '3'])
controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.0/24'], ['00:00:00:00:07:0D', '3'])

print("Plano de Control configurado correctamente con telemetría habilitada.")