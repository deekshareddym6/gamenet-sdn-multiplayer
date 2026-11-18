#!/usr/bin/env python3
"""Mininet topology for the Multiplayer Game Communication Network.

        h2 (player)  ---\\
        h3 (player)  ----- s1 ===(10 Mbps bottleneck)=== h1 (game server + noise sink)
        h4 (noise)   ---/

The ONLY bottleneck is the switch port towards the server (s1-eth1), shaped by Open vSwitch HTB queues:
  queue 0 = default / best-effort traffic, queue 1 = game traffic (guaranteed 7 Mbps).
Start Ryu first:  ryu-manager controller.py        Then:  sudo python3 topo.py"""
import os
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel
HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, 'logs')


def build():
    """Create, start and configure the network. Returns (net, hosts-dict)."""
    net = Mininet(controller=None, switch=OVSKernelSwitch, autoSetMacs=True)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    h = {i: net.addHost(f'h{i}', ip=f'10.0.0.{i}/24') for i in (1, 2, 3, 4)}
    net.addLink(h[1], s1)            # first link => port s1-eth1 (server port)
    for i in (2, 3, 4): net.addLink(h[i], s1)
    net.start()
    # Bottleneck + QoS queues on the server-facing port (egress s1 -> h1)
    s1.cmd('ovs-vsctl -- set port s1-eth1 qos=@q -- '
           '--id=@q create qos type=linux-htb other-config:max-rate=10000000 queues:0=@q0 queues:1=@q1 -- '
           '--id=@q0 create queue other-config:max-rate=10000000 other-config:min-rate=1000000 -- '
           '--id=@q1 create queue other-config:max-rate=10000000 other-config:min-rate=7000000')
    return net, h, s1


def start_server(h):
    h[1].cmd(f'python3 {HERE}/game_server.py > {LOGS}/server.out 2>&1 &')
    h[1].cmd(f'python3 {HERE}/noise.py --sink --port 5001 > /dev/null 2>&1 &')


def run():
    net, h, s1 = build()
    print('*** pingall'); net.pingAll()
    start_server(h)
    print('*** Server running on h1 (UDP 5000). Noise sink on h1 (UDP 5001). h4 = congestion source.')
    print('*** Players:   h2 python3 game_client.py --name alice --server 10.0.0.1 --duration 60 &')
    print('*** Congestion: h4 python3 noise.py --target 10.0.0.1 --mbps 20 --duration 20 &')
    print('*** QoS mode:  sh echo off > logs/qos_mode     (off | static | dynamic)')
    CLI(net); net.stop()


if __name__ == '__main__':
    setLogLevel('info'); os.makedirs(LOGS, exist_ok=True); run()
