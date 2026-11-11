#!/usr/bin/env python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call

def myNetwork():

    net = Mininet( topo=None,
                   build=False,
                   ipBase='10.0.0.0/8')

    info( '*** Adding controller\n' )
    c0=net.addController(name='c0',
                      controller=RemoteController,
                      ip='127.0.0.1',
                      protocol='tcp',
                      port=6633)

    info( '*** Add switches\n')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch)
    s2 = net.addSwitch('s2', cls=OVSKernelSwitch)
    s3 = net.addSwitch('s3', cls=OVSKernelSwitch)
    s4 = net.addSwitch('s4', cls=OVSKernelSwitch)
    s5 = net.addSwitch('s5', cls=OVSKernelSwitch)
    s6 = net.addSwitch('s6', cls=OVSKernelSwitch)

    info( '*** Add hosts\n')
    h1 = net.addHost('h1', cls=Host, ip='10.0.0.1/24', defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, ip='10.0.0.2/24', defaultRoute=None)
    h3 = net.addHost('h3', cls=Host, ip='10.0.0.3/24', defaultRoute=None)
    h4 = net.addHost('h4', cls=Host, ip='10.0.0.4/24', defaultRoute=None)
    h5 = net.addHost('h5', cls=Host, ip='10.0.0.5/24', defaultRoute=None)
    h6 = net.addHost('h6', cls=Host, ip='10.0.0.6/24', defaultRoute=None)

    info( '*** Add links\n')
    s1h1 = {'bw':40,'delay':'15ms'}
    net.addLink(s1, h1, cls=TCLink , **s1h1)
    s2h2 = {'bw':40,'delay':'15ms'}
    net.addLink(s2, h2, cls=TCLink , **s2h2)
    s3h3 = {'bw':40,'delay':'15ms'}
    net.addLink(s3, h3, cls=TCLink , **s3h3)
    s4h4 = {'bw':40,'delay':'15ms'}
    net.addLink(s4, h4, cls=TCLink , **s4h4)
    s5h5 = {'bw':40,'delay':'15ms'}
    net.addLink(s5, h5, cls=TCLink , **s5h5)
    s6h6 = {'bw':40,'delay':'15ms'}
    net.addLink(s6, h6, cls=TCLink , **s6h6)
    s1s2 = {'bw':40,'delay':'5ms'}
    net.addLink(s1, s2, cls=TCLink , **s1s2)
    s2s3 = {'bw':40,'delay':'10ms'}
    net.addLink(s2, s3, cls=TCLink , **s2s3)
    s4s5 = {'bw':40,'delay':'15ms'}
    net.addLink(s4, s5, cls=TCLink , **s4s5)
    s5s6 = {'bw':40,'delay':'20ms'}
    net.addLink(s5, s6, cls=TCLink , **s5s6)
    s1s4 = {'bw':40,'delay':'8ms'}
    net.addLink(s1, s4, cls=TCLink , **s1s4)
    s2s5 = {'bw':40,'delay':'12ms'}
    net.addLink(s2, s5, cls=TCLink , **s2s5)
    s3s6 = {'bw':40,'delay':'7ms'}
    net.addLink(s3, s6, cls=TCLink , **s3s6)
    s1s5 = {'bw':40,'delay':'18ms'}
    net.addLink(s1, s5, cls=TCLink , **s1s5)
    s2s4 = {'bw':40,'delay':'6ms'}
    net.addLink(s2, s4, cls=TCLink , **s2s4)
    s2s6 = {'bw':40,'delay':'14ms'}
    net.addLink(s2, s6, cls=TCLink , **s2s6)
    s3s5 = {'bw':40,'delay':'9ms'}
    net.addLink(s3, s5, cls=TCLink , **s3s5)

    info( '*** Starting network\n')
    net.build()
    info( '*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info( '*** Starting switches\n')
    net.get('s1').start([c0])
    net.get('s2').start([c0])
    net.get('s3').start([c0])
    net.get('s4').start([c0])
    net.get('s5').start([c0])
    net.get('s6').start([c0])

    info( '*** Post configure switches and hosts\n')

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()

