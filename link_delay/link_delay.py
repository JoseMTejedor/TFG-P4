from p4utils.utils.sswitch_p4runtime_API import SimpleSwitchP4RuntimeAPI

# Switch A
controller = SimpleSwitchP4RuntimeAPI(device_id=1, grpc_port=9559,
                                      p4rt_path='link_delay_p4rt.txt',
                                      json_path='link_delay.json')

controller.reset_state()

#Adding entries to the switch tables
controller.table_set_default('ipv4_lpm','drop')
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.1.1/32'], ['00:00:00:00:00:01','1'])
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.3.0/24'], ['00:00:00:00:03:02','2'])
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.5.0/24'], ['00:00:00:00:05:02','3'])
#Entrada para indicar que va hacia el host 1, por lo que hay que quitar la cabecera personalizada
controller.table_add('remove_header_tbl', 'remove_header', ['1'])


# Switch B
controller = SimpleSwitchP4RuntimeAPI(device_id=2, grpc_port=9560,
                                      p4rt_path='link_delay_p4rt.txt',
                                      json_path='link_delay.json')

controller.reset_state()
#controller.table_clear('ipv4_lpm')
controller.table_set_default('ipv4_lpm','drop')
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.1.0/24'], ['00:00:00:00:01:02','2'])
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.3.1/32'], ['00:00:00:00:00:02','1'])
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.5.0/24'], ['00:00:00:00:05:03','3'])
controller.table_add('remove_header_tbl', 'remove_header', ['1'])


# Swicth C
controller = SimpleSwitchP4RuntimeAPI(device_id=3, grpc_port=9561,
                                      p4rt_path='link_delay_p4rt.txt',
                                      json_path='link_delay.json')

controller.reset_state()
#controller.table_clear('ipv4_lpm')
controller.table_set_default('ipv4_lpm','drop')
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.1.0/24'], ['00:00:00:00:01:03','2'])
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.3.0/24'], ['00:00:00:00:03:03','3'])
controller.table_add('ipv4_lpm', 'ipv4_forward',['10.0.5.1/32'], ['00:00:00:00:00:03','1'])
controller.table_add('remove_header_tbl', 'remove_header', ['1'])
