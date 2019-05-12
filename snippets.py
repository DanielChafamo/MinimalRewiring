from mininet.topo import Topo
from mininet.node import Switch
from mininet.node import Host
from mininet.net import Mininet
from mininet.cli import CLI
import time

class TopoController(Topo):
  def __init__(self):
    Topo.__init__(self)
    self.id = 1
    self.switches_ = {}
    self.hosts_ = {}

  def createSwitch(self, sw_id):
    name = 's%d'%sw_id
    self.switches_[name] = self.addSwitch(name)
  
  def createHost(self, host_id):
    name = 'h%d'%host_id
    self.hosts_[name] = self.addHost(name)

  def link(self, node1, node2):
    self.addLink(node1, node2)

if __name__ == "__main__":
    topo = TopoController()
    topo.createSwitch(1)
    topo.createSwitch(2)
    topo.createHost(1)
    topo.createHost(2)
    topo.createHost(3)
    time.sleep(1)
    print(topo.switches_)
    print(topo.hosts_)

    # add links
    topo.link('s1', 'h1')
    topo.link('s2', 'h2')
    topo.link('s2', 'h3')
    topo.link('s1', 's2')

    # tests
    net = Mininet(topo)
    net.pingAll(timeout=1)

    net.addSwitch('s3')
    net.addLink('s3', 'h2')

    cli = CLI(net)
    # TODO: instead of the above cli, do something like this
    def sendCommand(cmd_text):
      # this block should be done on a global scope
      # BEGIN - create network from topo, cli from network
      topo = TopoController()
      net = Mininet(topo)

      fd = open('somefile_preferrably_buffer')
      cli = CLI(net, stdin=fd)
      
      # END

      # now to send commands, write to buffer and do cli.readline()
      

    print("finished building topology")
