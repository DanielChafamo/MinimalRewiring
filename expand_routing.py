from ryu.base import app_manager
from ryu.controller import ofp_event, dpset
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.ip import ipv4_to_bin
from ryu.lib.packet import packet     
import random, math, json, sys
from time import sleep
from ILP import MinimalRewiringILP
from network import Network
from mininet.net import Mininet
from mininet.topo import Topo


class Controller(app_manager.RyuApp):
  def __init__(self):
    super(Controller, self).__init__()

    self.switches = {}      # Switches 
    self.num_switches = -1  # track that all switches have reported
    self.priority = 1100    # current max priority 
    self.numH = None        # number of hosts  
    self.verbose = 0        # reporting details 

    self.network = self.initial_network1()
    self.mininet_from_network(self.network)
    self.wiring, self.agg_key, self.core_key = self.network.core_agg_wiring()
    self.minwiring = MinimalRewiringILP(self.wiring)
    # wait a few secs and add new switch
    sleep(10)
    self.add_switch('spine', 5,2) 

  def mininet_from_network(self, network):
    """ Generate a mininet topology corresponding to the /network/ """
    self.topo = Topo()

    hosts = self.network.get_type('host')
    for sid in hosts:
      self.topo.addHost('s%d' % sid, dpid=("%0.2X" % sid))
    for sid in self.network.switches.keys():
      if sid not in hosts:
        self.topo.addSwitch('s%d' % sid, dpid=("%0.2X" % sid), 
                            protocols='OpenFlow10')

    for sid1, sid2 in self.network.edges.keys():
      self.addLink('s%d' % sid1, 's%d' % sid2)

    self.mininet = Mininet(self.topo)
    self.mininet.pingAll(timeout=1)

    return self.mininet

  @set_ev_cls(dpset.EventDP)
  def switchStatus(self, ev): 
    print("S %s: %s!" % (ev.dp.id, "connected" if ev.enter else "disconnected"))
    sys.stdout.flush()
    self.prepareSwitch(ev.dp)

  def prepareSwitch(self, sw):
    hostIp = int(sw.id)  
    self.switches[hostIp] = sw

    routes = self.network.route_ecmp()
    self.priority += 1
    for s_id in routes.keys():
      for h_id in routes[s_id].keys():
        self.install_flow(self.switches[s_id], 
                          (10 << 24) + h_id, routes[s_id][h_id], 
                          pr=self.priority)

  def install_flow(self, sw, dst, out, pr=1100, src=None): 
    # Send the ARP/IP packets to the proper host
    ofproto = sw.ofproto
    action = sw.ofproto_parser.OFPActionOutput(out)
    if not src:
      match = sw.ofproto_parser.OFPMatch(dl_type=0x806, nw_dst=dst) 
      match_arp = sw.ofproto_parser.OFPMatch(dl_type=0x800, nw_dst=dst) 
    else:
      match = sw.ofproto_parser.OFPMatch(dl_type=0x806, nw_dst=dst, nw_src=src) 
      match_arp = sw.ofproto_parser.OFPMatch(dl_type=0x800, nw_dst=dst, nw_src=src)
    mod = sw.ofproto_parser.OFPFlowMod(
            datapath=sw, match=match, cookie=0,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=pr,
            flags=ofproto.OFPFF_SEND_FLOW_REM, 
            actions=[action])
    sw.send_msg(mod)

    mod = sw.ofproto_parser.OFPFlowMod(
            datapath=sw, match=match_arp, cookie=0,
            command=ofproto.OFPFC_ADD, idle_timeout=0, hard_timeout=0,
            priority=pr,
            flags=ofproto.OFPFF_SEND_FLOW_REM, 
            actions=[action])
    sw.send_msg(mod)

  def add_switch(self, level, nports, pace=2):
    """ Add spine or server block switch with /nports/ complete with all 
    necessary rewiring and rerouting

    Args:
          level (string): "spine" or "server"
          nports (int): number of ports on switch
          pace (int): number of instructions to install before rerouting

    """
    self.network.max_sid += 1 
    sid = self.network.max_sid 
    self.mininet.addSwitch('s%d' % sid, dpid=("%0.2X" % sid), 
                            protocols='OpenFlow10')
    if level == 'spine':
      stype = 'core'
      self.core_key[len(self.core_key)] = sid
    else: 
      stype = 'agg'
      self.agg_key[len(self.agg_key)] = sid

    self.network.add_switch(sid, nports, stype)

    instructions = self.minwiring.rewire(level, nports)
    for i, instr in enumerate(instructions):
      # add or delete link from network state and mininet topology
      a_id = self.agg_key[instr[1]]
      c_id = self.core_key[instr[2]]
      if instr[0] == "CONNECT":
        self.network.add_link(a_id, c_id, 1)
        self.mininet.addLink('s%d' % a_id, 's%d' % c_id)
        print("Adding 1 link between switch {} and {}".format(a_id, c_id))
      elif instr[0] == "DISCONNECT":
        self.network.remove_link(a_id, c_id, 1)
        self.mininet.delLink('s%d' % a_id, 's%d' % c_id)
        print("Removing 1 link between switch {} and {}".format(a_id, c_id))

      if i % pace == 0:
        # reroute every pace instructions
        routes = self.network.route_ecmp()
        self.priority += 1
        for s_id in routes.keys():
          for h_id in routes[s_id].keys():
            self.install_flow(self.switches[s_id], 
                              (10 << 24) + h_id, routes[s_id][h_id], 
                              pr=self.priority)

    # Final rerouting before exit        
    routes = self.network.route_ecmp()
    self.priority += 1
    for s_id in routes.keys():
      for h_id in routes[s_id].keys():
        self.install_flow(self.switches[s_id], 
                          (10 << 24) + h_id, routes[s_id][h_id], 
                          pr=self.priority)

  def initial_network1(self):
    """ Sample starting network onto which we'll add nodes """
    net = Network()

    for i in range(1,9):
      net.add_switch(i,4,'host')
    for i in range(9,13):
      net.add_switch(i,4,'edge')
    for i in range(13,17):
      net.add_switch(i,5,'agg')
    for i in range(17,19):
      net.add_switch(i,6,'core')

    # host:edge links
    h_e = [(1,9,1),(2,9,1),(3,10,1),(4,10,1),(5,11,1),(6,11,1),(7,12,1),(8,12,1)] 
    # edge:agg links
    e_a = [(13,9,1),(14,9,1),(13,10,1),(14,10,1),(15,11,1),(16,11,1),(15,12,1),(16,12,1)]
    # agg:core links
    a_c = [(13,17,2),(14,17,1),(13,18,1),(14,18,2),(15,17,2),(16,17,1),(15,18,1),(16,18,2)] 

    for link in h_e + e_a + a_c:
      print(link)
      net.add_link(*link)
    return net

