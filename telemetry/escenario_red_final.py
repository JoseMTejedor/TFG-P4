#!/usr/bin/env python3
from p4utils.mininetlib.network_API import NetworkAPI

net = NetworkAPI()

# level of logging
net.setLogLevel('info')

# Creates P4 switches, in particular bmv2 switches of target simple_switch_grpc
net.addP4RuntimeSwitch('sA')
net.addP4RuntimeSwitch('sB')
net.addP4RuntimeSwitch('sC')
net.addP4RuntimeSwitch('sD')
net.addP4RuntimeSwitch('sE')
net.addP4RuntimeSwitch('sF')
net.addP4RuntimeSwitch('sG')

#Switch tradicional para gestión OOB
net.addSwitch('s_mgmt', failMode='standalone')

# Creates hosts
net.addHost('h1')
net.addHost('h2')
net.addHost('h3')
net.addHost('h4')
net.addHost('h5')
net.addHost('h6')
net.addHost('h_col') #Host que hará la función de servidor en el que se guardarán los datos de telemetría

# CREATES LINKS
# Host links
net.addLink('h1', 'sA')
net.addLink('h2', 'sC')
net.addLink('h3', 'sE')
net.addLink('h4', 'sA')
net.addLink('h5', 'sD')
net.addLink('h6', 'sD')
net.addLink('h_col', 's_mgmt')

# Switches links Hexagon
net.addLink('sA', 'sB')
net.addLink('sB', 'sC')
net.addLink('sC', 'sD')
net.addLink('sD', 'sE')
net.addLink('sE', 'sF')
net.addLink('sF', 'sA')

# Centre links
net.addLink('sA', 'sG')
net.addLink('sG', 'sD')

# Telemetry links
net.addLink('sA', 's_mgmt')
net.addLink('sB', 's_mgmt')
net.addLink('sC', 's_mgmt')
net.addLink('sD', 's_mgmt')
net.addLink('sE', 's_mgmt')
net.addLink('sF', 's_mgmt')
net.addLink('sG', 's_mgmt')

# ASIGNACIÓN DE PUERTOS

# Host a Switches (Puerto 1 en switch, Puerto 0 en host)
# Para los segundos host usaremos el Puerto 2 del switch
net.setIntfPort('sA', 'h1', 1) 
net.setIntfPort('h1', 'sA', 0)

net.setIntfPort('sC', 'h2', 1)
net.setIntfPort('h2', 'sC', 0) 

net.setIntfPort('sE', 'h3', 1) 
net.setIntfPort('h3', 'sE', 0)

net.setIntfPort('sA', 'h4', 6) 
net.setIntfPort('h4', 'sA', 0)

net.setIntfPort('sD', 'h5', 1) 
net.setIntfPort('h5', 'sD', 0)

net.setIntfPort('sD', 'h6', 6) 
net.setIntfPort('h6', 'sD', 0)

# h_col al switches tradicional(Puerto 8 al switch, Puerto 0 en h_col)
net.setIntfPort('s_mgmt', 'h_col', 8) 
net.setIntfPort('h_col', 's_mgmt', 0)


# Switches en el anillo hexagonal (Puertos 2 (conexiones a la derecha) y 3 (conexiones a la izquierda))
net.setIntfPort('sA', 'sB', 2)
net.setIntfPort('sB', 'sA', 3)

net.setIntfPort('sB', 'sC', 2)
net.setIntfPort('sC', 'sB', 3)

net.setIntfPort('sC', 'sD', 2)
net.setIntfPort('sD', 'sC', 3)

net.setIntfPort('sD', 'sE', 2)
net.setIntfPort('sE', 'sD', 3)

net.setIntfPort('sE', 'sF', 2)
net.setIntfPort('sF', 'sE', 3)

net.setIntfPort('sF', 'sA', 2)
net.setIntfPort('sA', 'sF', 3)

# Enlaces con el switch central
net.setIntfPort('sA', 'sG', 4)
net.setIntfPort('sG', 'sA', 2)

net.setIntfPort('sD', 'sG', 4)
net.setIntfPort('sG', 'sD', 3)

# Enlaces red de gestión telemetria (Todos los Swithces P4 usan el Puerto 5)
net.setIntfPort('sA', 's_mgmt', 5)
net.setIntfPort('sB', 's_mgmt', 5)
net.setIntfPort('sC', 's_mgmt', 5)
net.setIntfPort('sD', 's_mgmt', 5)
net.setIntfPort('sE', 's_mgmt', 5)
net.setIntfPort('sF', 's_mgmt', 5)
net.setIntfPort('sG', 's_mgmt', 5)

net.setIntfPort('s_mgmt', 'sA', 1)
net.setIntfPort('s_mgmt', 'sB', 2)
net.setIntfPort('s_mgmt', 'sC', 3)
net.setIntfPort('s_mgmt', 'sD', 4)
net.setIntfPort('s_mgmt', 'sE', 5)
net.setIntfPort('s_mgmt', 'sF', 6)
net.setIntfPort('s_mgmt', 'sG', 7)

# ASIGNACIÓN DE LAS DIRECCIONES IP A LAS INTERFACES

# Host a Switches(/24)
net.setIntfIp('h1', 'sA', '10.0.1.1/24')
net.setIntfIp('sA', 'h1', '10.0.1.5/24')

net.setIntfIp('h2', 'sC', '10.0.3.1/24')
net.setIntfIp('sC', 'h2', '10.0.3.5/24')

net.setIntfIp('h3', 'sE', '10.0.5.1/24') 
net.setIntfIp('sE', 'h3', '10.0.5.5/24')

net.setIntfIp('h4', 'sA', '10.0.1.2/24')
net.setIntfIp('sA', 'h4', '10.0.1.6/24')

net.setIntfIp('h5', 'sD', '10.0.4.1/24')
net.setIntfIp('sD', 'h5', '10.0.4.5/24')

net.setIntfIp('h6', 'sD', '10.0.4.2/24')
net.setIntfIp('sD', 'h6', '10.0.4.6/24')

# Colector (/24)
net.setIntfIp('h_col', 's_mgmt', '10.99.0.100/24')

# Enlaces Hexágono(/30)
net.setIntfIp('sA', 'sB', '192.168.0.1/30')
net.setIntfIp('sB', 'sA', '192.168.0.2/30')

net.setIntfIp('sB', 'sC', '192.168.0.5/30') 
net.setIntfIp('sC', 'sB', '192.168.0.6/30')  

net.setIntfIp('sC', 'sD', '192.168.0.9/30') 
net.setIntfIp('sD', 'sC', '192.168.0.10/30')

net.setIntfIp('sD', 'sE', '192.168.0.13/30') 
net.setIntfIp('sE', 'sD', '192.168.0.14/30')

net.setIntfIp('sE', 'sF', '192.168.0.17/30') 
net.setIntfIp('sF', 'sE', '192.168.0.18/30')

net.setIntfIp('sF', 'sA', '192.168.0.21/30') 
net.setIntfIp('sA', 'sF', '192.168.0.22/30')

# Enlaces Centrales (/30)
net.setIntfIp('sA', 'sG', '192.168.0.25/30')
net.setIntfIp('sG', 'sA', '192.168.0.26/30')

net.setIntfIp('sD', 'sG', '192.168.0.29/30') 
net.setIntfIp('sG', 'sD', '192.168.0.30/30')

# Direcciones IP de los puertos de telemetría (Puerto 5) hacia la red OOB
net.setIntfIp('sA', 's_mgmt', '10.99.0.1/24')
net.setIntfIp('sB', 's_mgmt', '10.99.0.2/24')
net.setIntfIp('sC', 's_mgmt', '10.99.0.3/24')
net.setIntfIp('sD', 's_mgmt', '10.99.0.4/24')
net.setIntfIp('sE', 's_mgmt', '10.99.0.5/24')
net.setIntfIp('sF', 's_mgmt', '10.99.0.6/24')
net.setIntfIp('sG', 's_mgmt', '10.99.0.7/24')

# ASIGNACIÓN DE DIRECCIONES MAC
# MACs de los Hosts (00:00:00:00:00:XX)
net.setIntfMac('h1', 'sA', '00:00:00:00:00:01')
net.setIntfMac('h2', 'sC', '00:00:00:00:00:02')
net.setIntfMac('h3', 'sE', '00:00:00:00:00:03')
net.setIntfMac('h4', 'sA', '00:00:00:00:00:04')
net.setIntfMac('h5', 'sD', '00:00:00:00:00:05')
net.setIntfMac('h6', 'sD', '00:00:00:00:00:06')
net.setIntfMac('h_col', 's_mgmt', '00:00:00:99:99:99')

# MACs de los switches en los puertos hacia los hosts (00:00:00:00:01:XX)
net.setIntfMac('sA', 'h1', '00:00:00:00:01:0A') 
net.setIntfMac('sC', 'h2', '00:00:00:00:01:0C') 
net.setIntfMac('sE', 'h3', '00:00:00:00:01:0E')
net.setIntfMac('sA', 'h4', '00:00:00:00:01:1A') 
net.setIntfMac('sD', 'h5', '00:00:00:00:01:0D') 
net.setIntfMac('sD', 'h6', '00:00:00:00:01:1D')  

# MACs de los enlaces del Anillo Hexagonal (00:00:00:00:Origen:Destino)
net.setIntfMac('sA', 'sB', '00:00:00:00:0A:0B')
net.setIntfMac('sB', 'sA', '00:00:00:00:0B:0A')

net.setIntfMac('sB', 'sC', '00:00:00:00:0B:0C')
net.setIntfMac('sC', 'sB', '00:00:00:00:0C:0B')

net.setIntfMac('sC', 'sD', '00:00:00:00:0C:0D') 
net.setIntfMac('sD', 'sC', '00:00:00:00:0D:0C')

net.setIntfMac('sD', 'sE', '00:00:00:00:0D:0E') 
net.setIntfMac('sE', 'sD', '00:00:00:00:0E:0D')

net.setIntfMac('sE', 'sF', '00:00:00:00:0E:0F')
net.setIntfMac('sF', 'sE', '00:00:00:00:0F:0E')

net.setIntfMac('sF', 'sA', '00:00:00:00:0F:0A') 
net.setIntfMac('sA', 'sF', '00:00:00:00:0A:0F')

# 4. MACs de los enlaces Centrales (Atajos)
net.setIntfMac('sA', 'sG', '00:00:00:00:0A:07') 
net.setIntfMac('sG', 'sA', '00:00:00:00:07:0A')

net.setIntfMac('sD', 'sG', '00:00:00:00:0D:07') 
net.setIntfMac('sG', 'sD', '00:00:00:00:07:0D')

# 5. MACs de los puertos de Gestión (OOB - Puerto 5), usamos '99' para denotar la red de gestión
net.setIntfMac('sA', 's_mgmt', '00:00:00:00:0A:99')
net.setIntfMac('sB', 's_mgmt', '00:00:00:00:0B:99')
net.setIntfMac('sC', 's_mgmt', '00:00:00:00:0C:99')
net.setIntfMac('sD', 's_mgmt', '00:00:00:00:0D:99')
net.setIntfMac('sE', 's_mgmt', '00:00:00:00:0E:99')
net.setIntfMac('sF', 's_mgmt', '00:00:00:00:0F:99')
net.setIntfMac('sG', 's_mgmt', '00:00:00:00:07:99')

# Adds default routes in hosts
net.setDefaultRoute('h1', '10.0.1.5')
net.setDefaultRoute('h2', '10.0.3.5')
net.setDefaultRoute('h3', '10.0.5.5')
net.setDefaultRoute('h4', '10.0.1.6')
net.setDefaultRoute('h5', '10.0.4.5')
net.setDefaultRoute('h6', '10.0.4.6')

# Creates log files for the switches (available in log)
net.enableLogAll()

# Start the network
net.startNetwork()
