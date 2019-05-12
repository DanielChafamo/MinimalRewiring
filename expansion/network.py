import numpy as np
import networkx as nx 
from collections import defaultdict
import json 

class Switch(object):
  def __init__(self, nid, nports, stype, num):
    self.nid = nid        # switch id
    self.stype = stype    # type: host, edge, agg or core
    self.num = num        # id within type
    self.nports = nports  # number of ports
    self.nlinks = 0       # number of links total
    self.uplinks = 0      # number of uplinks
    self.links = {}       # links: nid -> [port# ]

  def __str__(self):
    string = "Switch {}, of type '{}', with {} ports\n"\
      .format(self.nid, self.stype, self.nports)
    string += "Has {} links, with {} of them pointing up\n"\
      .format(self.nlinks, self.uplinks)
    lnks = ", ".join(["Switch {} at ports {}"\
                     .format(nid, self.links[nid]) for nid in self.links.keys()])
    string += "Linked to {}".format(lnks)
    return string


class Network(object):
  """ Network state class
  """
  def __init__(self):
    self.edges = defaultdict(int)         # edges[(nid1, nid2)] = num_links
    self.switches = {}                    # nodes[nid] = {'type', 'nports', 'num'}
    self.routes = defaultdict(dict)       # routes[id] = {dst : port_num}
    self.max_sid = 0                      # largest switch id in network

    self.counts = {'host':0, 'edge':0, 'agg':0, 'core':0}

  def add_switch(self, sid, nports, stype):
    self.max_sid = max(self.max_sid, sid)
    self.switches[nid] = Switch(sid, nports, stype, self.counts[stype])
    self.counts[stype] += 1

  def add_link(self, nid1, nid2, count):
    """ Add /count/ links between switches /nid1/ and /nid2/"""

    if nid1 not in self.switches.keys() or nid2 not in self.switches.keys():
      raise KeyError('Trying to insert edge at unrecognized node.')

    if self.switches[nid1].nlinks + count > self.switches[nid1].nports or \
      self.switches[nid2].nlinks+ count > self.switches[nid2].nports:
      raise Exception('Not enough ports for edge.')

    nport1 = self.switches[nid1].nlinks+1
    self.switches[nid1].links[nid2] =  [nport1+i for i in range(count)]
    nport2 = self.switches[nid2].nlinks+1
    self.switches[nid2].links[nid1] =  [nport2+i for i in range(count)]

    self.switches[nid1].nlinks += count 
    self.switches[nid2].nlinks += count 

    if self.is_up(nid1, nid2):
      self.switches[nid1].uplinks += count 
    else:
      self.switches[nid2].uplinks += count 

    self.edges[(nid1, nid2)] += count

  def remove_link(self, nid1, nid2, count):
    """ Remove /count/ links between switches /nid1/ and /nid2/"""

    if nid1 not in self.switches.keys() or nid2 not in self.switches.keys():
      raise KeyError('Trying to insert edge at unrecognized node.')

    if len(self.switches[nid1].links[nid2]) - count < 0:
      raise Exception('Not enough links to remove between nodes.')
 
    self.switches[nid1].links[nid2] = self.switches[nid1].links[nid2][:-count] 
    self.switches[nid2].links[nid1] = self.switches[nid2].links[nid1][:-count] 

    self.switches[nid1].nlinks -= count 
    self.switches[nid2].nlinks -= count 

    if self.is_up(nid1, nid2):
      self.switches[nid1].uplinks -= count 
    else:
      self.switches[nid2].uplinks -= count 

    self.edges[(nid1, nid2)] -= count

  def route_ecmp(self):
    """ Compute ECMP routing paths for each switch in the network """
    # routing for edges
    for e_id in self.get_type('edge'):
      # uplink ports to distribute over
      n_uplinks = self.switches[e_id].uplinks
      nports = self.switches[e_id].nports 
      up_ports = list(range(nports - n_uplinks + 1, nports + 1))
      count = 0

      for h_id in self.get_type('host'):
        if self.linked(e_id, h_id):
          self.routes[e_id][h_id] = self.switches[e_id].links[h_id][0]
        else:
          self.routes[e_id][h_id] = up_ports[count % n_uplinks]
          count += 1

    # routing for aggs
    for a_id in self.get_type('agg'):
      # hosts within agg switches' pod 
      hosts = {} 
      for e_id in self.switches[a_id].links.keys():
        if self.switches[e_id].stype == 'edge':
          for h_id in self.switches[e_id].links.keys():
            if self.switches[h_id].stype == 'host':
              hosts[h_id] = e_id

      # uplink ports to distribute over
      n_uplinks = self.switches[a_id].uplinks
      nports = self.switches[a_id].nports 
      up_ports = list(range(nports - n_uplinks + 1, nports + 1))
      count = 0

      for h_id in self.get_type('host'):
        if h_id in hosts.keys(): 
          e_id = hosts[h_id]
          self.routes[a_id][h_id] = self.switches[a_id].links[e_id][0]
        else:
          self.routes[a_id][h_id] = up_ports[count % n_uplinks]
          count += 1

    # routing for core
    for c_id in self.get_type('core'):
      # map host to list of agg switches that can lead to host
      hosts = defaultdict(list)
      for a_id in self.switches[c_id].links.keys():
        for e_id in self.switches[a_id].links.keys():
          if self.switches[e_id].stype == 'edge':
            for h_id in self.switches[e_id].links.keys():
              if self.switches[h_id].stype == 'host':
                hosts[h_id].append(a_id) 

      # randomly choose one of the mapped agg switches
      for h_id in self.get_type('host'): 
        a_ids = hosts[h_id]
        opt_ports = []
        for a_id in a_ids:
          opt_ports += self.switches[c_id].links[a_id]
        self.routes[c_id][h_id] = np.random.choice(opt_ports) 

    return self.routes


  def is_up(self, nid1, nid2):
    level = {'host':1, 'edge':2, 'agg':3, 'core':4}
    return level[self.switches[nid1].stype] < level[self.switches[nid2].stype]

  def get_type(self, _type):
    switches = []
    for idx in self.switches.keys():
      if self.switches[idx].stype == _type:
        switches.append(idx)
    return switches

  def linked(self, nid1, nid2):
    return (nid1, nid2) in self.edges.keys() or (nid2, nid1) in self.edges.keys()

  def to_nx(self):
    G = nx.Graph()
    G.add_nodes_from(self.switches.keys())
    for nid in G.nodes(): 
      G.node[nid]['type'] = self.switches[nid].stype
      G.node[nid]['num'] = self.switches[nid].num

    G.add_edges_from(self.edges.keys())
    for edge in G.edges:
      G.edges[edge]["count"] = self.edges[edge]
    return G

  def graph_traffic_matrix(self, matrix):
    pass

  def core_agg_wiring(self):
    """ Generate wiring matrix between core and agg levels """
    core_key = {sid:i for i, sid in enumerate(self.get_type('core'))}
    agg_key = {sid:i for i, sid in enumerate(self.get_type('agg'))}
    wiring = np.zeros((len(core_key), len(agg_key)))
    for c_id in core_key.keys():
      for a_id in self.switches[c_id].links.keys():
        wiring[core_key[c_id],agg_key[a_id]] = len(self.switches[c_id].links[a_id])
    return wiring, core_key.update(agg_key)

  def write_graph(self):
    """ Write json graph for visualization purposes """
    G = self.to_nx()
    g = nx.readwrite.json_graph.node_link_data(G)
    with open('../CloudNetVis/netvis/static/netvis/traffic/traffic.json', 'w') as fp:
      json.dump(g, fp, indent=4)


