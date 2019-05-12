from ryu.base import app_manager
from ryu.controller import ofp_event, dpset
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.ip import ipv4_to_bin
from ryu.lib.packet import packet    
from time import sleep
from collections import defaultdict
from copy import deepcopy
import random, math, json, sys
from ILP import MinimalRewiringILP
from network import Network


class Controller(app_manager.RyuApp):
    def __init__(self):
        super(Controller, self).__init__()

        self.switches = {}      # Switches 
        self.num_edges = -1     # track that all edge switches have reported
        self.priority = 1100    # current max priority 
        self.numH = None        # number of hosts  
        self.verbose = 0        # reporting details 

    # 
    # Static routing
    # 
    @set_ev_cls(dpset.EventDP)
    def switchStatus(self, ev): 
        print("S %s: %s!" % (ev.dp.id, "connected" if ev.enter else "disconnected"))
        sys.stdout.flush()
        self.prepareSwitch(ev.dp)

    def prepareSwitch(self, sw):
        hostIp = int(sw.id) - 1 
        ofproto = sw.ofproto 


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

