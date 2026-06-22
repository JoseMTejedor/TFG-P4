#!/usr/bin/env python3
from p4utils.mininetlib.network_API import NetworkAPI

net = NetworkAPI()

# level of logging
net.setLogLevel('info')


# The P4 program can be compiled and the controller executed from this script, but we will do it manually

# The P4 program basico.p4 can be compiled from this script with these two sentences:
#net.setCompiler(p4rt=True)
#net.setP4SourceAll('basico.p4')  

# The controller controlador.py can be executed from this script with this sentence: 
#net.execScript('python3 controlador.py', reboot=True) 

# Creates P4 switches, in particular bmv2 switches of target simple_switch_grpc
net.addP4RuntimeSwitch('sA')
net.addP4RuntimeSwitch('sB')
net.addP4RuntimeSwitch('sC')

# Creates hosts
net.addHost('h1')
net.addHost('h2')
net.addHost('h3')

# Creates links
net.addLink('h1', 'sA')
net.addLink('h2', 'sB')
net.addLink('sA', 'sB')
net.addLink('h3', 'sC')
net.addLink('sA', 'sC')
net.addLink('sB', 'sC')

# Assignment  of port number for each link in each node
net.setIntfPort('sA', 'h1', 1) 
net.setIntfPort('h1', 'sA', 0) 
net.setIntfPort('sA', 'sB', 2) 
net.setIntfPort('sA', 'sC', 3)  
net.setIntfPort('sB', 'h2', 1)
net.setIntfPort('h2', 'sB', 0)  
net.setIntfPort('sB', 'sA', 2) 
net.setIntfPort('sB', 'sC', 3) 
net.setIntfPort('sC', 'h3', 1) 
net.setIntfPort('h3', 'sC', 0) 
net.setIntfPort('sC', 'sA', 2) 
net.setIntfPort('sC', 'sB', 3) 

# Assignment of IP addresses to interfaces
net.setIntfIp('h1', 'sA', '10.0.1.1/24')
net.setIntfIp('sA', 'h1', '10.0.1.5/24') 
net.setIntfIp('sA', 'sB', '192.168.0.1/30')
net.setIntfIp('sB', 'sA', '192.168.0.2/30')  
net.setIntfIp('sA', 'sC', '192.168.0.5/30') 
net.setIntfIp('sC', 'sA', '192.168.0.6/30')  
net.setIntfIp('h2', 'sB', '10.0.3.1/24')
net.setIntfIp('sB', 'h2', '10.0.3.5/24') 
net.setIntfIp('sB', 'sC', '192.168.0.9/30') 
net.setIntfIp('sC', 'sB', '192.168.0.10/30')
net.setIntfIp('h3', 'sC', '10.0.5.1/24') 
net.setIntfIp('sC', 'h3', '10.0.5.5/24') 

# Assignment of MAC addresses to interfaces
net.setIntfMac('h1', 'sA', '00:00:00:00:00:01')
net.setIntfMac('sA', 'h1', '00:00:00:00:01:01') 
net.setIntfMac('sA', 'sB', '00:00:00:00:01:02')
net.setIntfMac('sB', 'sA', '00:00:00:00:03:02')  
net.setIntfMac('sA', 'sC', '00:00:00:00:01:03') 
net.setIntfMac('sC', 'sA', '00:00:00:00:05:02')  
net.setIntfMac('h2', 'sB', '00:00:00:00:00:02')
net.setIntfMac('sB', 'h2', '00:00:00:00:03:01') 
net.setIntfMac('sB', 'sC', '00:00:00:00:03:03') 
net.setIntfMac('sC', 'sB', '00:00:00:00:05:03')
net.setIntfMac('h3', 'sC', '00:00:00:00:00:03') 
net.setIntfMac('sC', 'h3', '00:00:00:00:05:01') 

# Adds default routes in hosts
net.setDefaultRoute('h1', '10.0.1.5')
net.setDefaultRoute('h2', '10.0.3.5')
net.setDefaultRoute('h3', '10.0.5.5')

# Any of these commands allows an automatic asignment of IP and MAC addresses, the difference is in the created number of IP subnetworks 
#net.l2()
#net.mixed()
#net.l3()

# Creates traffic capture files (.pcap) for the switches interfaces
#net.enablePcapDumpAll()

# Creates log files for the switches (available in log)
net.enableLogAll()

# Start the network
net.startNetwork()
