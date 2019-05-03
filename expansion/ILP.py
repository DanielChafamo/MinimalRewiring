import numpy as np
import cvxpy as cp


# keep track of server and spine blocks and the number of ports in each
class SwitchSet(object):
  def __init__(self, num_server=None, 
                     num_spine=None,
                     server_numports=None,
                     spine_numports=None):
    self.num_server = num_server
    self.num_spine = num_spine
    self.server_numports = server_numports
    self.spine_numports = spine_numports

  def from_wiring_matrix(self, wiring_matrix):
    self.num_server = wiring_matrix.shape[0]         
    self.num_spine = wiring_matrix.shape[1] 
    self.server_numports = wiring_matrix.sum(axis=1)
    self.spine_numports = wiring_matrix.sum(axis=0)


class MinimalRewiringILP(object):
  def __init__(self, initial_wiring):
    self.switch_set = SwitchSet()
    self.switch_set.from_wiring_matrix(initial_wiring)
    self.current_wiring = initial_wiring

  def rewire(self, level, num_ports):
    # update switch set
    if level == "spine":
      self.switch_set.num_spine += 1
      self.switch_set.spine_numports = np.append(self.switch_set.spine_numports, num_ports)
    else:
      self.switch_set.num_server += 1
      self.switch_set.server_numports = np.append(self.switch_set.server_numports, num_ports)

    self.nsp = self.switch_set.num_spine
    self.nsv = self.switch_set.num_server
    # prepare ILP equations
    self.prepare_variables()
    self.prepare_constraints()
    self.prepare_objective()

    # run ILP
    problem = cp.Problem(cp.Minimize(self.objective), self.constraints)
    problem.solve()
    
    new_wiring = self.variables.value[:self.nsp*self.nsv].reshape(self.nsv, self.nsp)
    old_wiring = np.zeros([self.nsv, self.nsp])
    old_wiring[:self.current_wiring.shape[0],:self.current_wiring.shape[1]] = self.current_wiring
    
    # identify link movements
    lm = self.link_moves(old_wiring.astype(np.int), new_wiring.astype(np.int))

    # update wiring 
    self.current_wiring = new_wiring.astype(np.int)

    return lm

  def prepare_variables(self): 
    self.variables = cp.Variable(self.nsp*self.nsv*2, integer=True)
    return self.variables

  def varidx(self, _type, i, j):
    if _type == "x":
      return i*self.nsp + j 
    else:
      return self.nsp*self.nsv + i*self.nsv + j

  def curr_wiring(self, i, j):
    if i >= self.current_wiring.shape[0] or j >= self.current_wiring.shape[1]:
      return 0
    else:
      return self.current_wiring[i][j]


  def prepare_constraints(self):  
    # non negative link counts
    self.constraints = [self.variables[i] >=0 for i in range(self.nsp*self.nsv)]

    # num of ports constraints [link conservation] 
    for i in range(self.nsv):
      self.constraints += [
          np.ones(self.nsp)@self.variables[[self.varidx("x",i,j) for j in range(self.nsp)]] <= \
          self.switch_set.server_numports[i]
        ]

    for j in range(self.nsp):
      self.constraints += [
          np.ones(self.nsv)@self.variables[[self.varidx("x",i,j) for i in range(self.nsv)]] <= \
          self.switch_set.spine_numports[j]
        ]

    # capacity[even distribution] constraints  
    for i in range(self.nsv):
      k = self.switch_set.server_numports[i] / float(self.nsp)
      self.constraints += [
          self.variables[self.varidx("x",i,j)] >= np.floor(k) for j in range(self.nsp)
        ]
      self.constraints += [
          self.variables[self.varidx("x",i,j)] <= np.ceil(k) for j in range(self.nsp) 
        ]

    # constraints to make optimization of absolute values of difference
    for i in range(self.nsv):
      for j in range(self.nsp):
        self.constraints += [self.variables[self.varidx("x_p",i,j)] >= self.variables[self.varidx("x",i,j)] - self.curr_wiring(i,j) ]
        self.constraints += [self.variables[self.varidx("x_p",i,j)] >= -1*(self.variables[self.varidx("x",i,j)] - self.curr_wiring(i,j)) ]
      
  def prepare_objective(self):
    self.objective = 0
    for i in range(2*self.nsv*self.nsp):
      if i < self.nsv*self.nsp:
        # try to utilize as much of the links as possible
        self.objective -= self.variables[i]
      else:
        # minimize difference from initial wiring
        self.objective += self.variables[i]

  def link_moves(self, current_wiring, final_wiring):
    capacity = self.switch_set.spine_numports
    changes = self.ConnectDisconnect(current_wiring, final_wiring)
    rewires = []
    while len(changes) > 0:
        actions, changes_p, new_capacity = self.swap(changes, capacity)
        rewires += actions
        changes = changes_p
        capacity = new_capacity
    return rewires

  def ConnectDisconnect(self, initial, final):
    disconnect = []
    connect = []
    log = []
    for i in range(len(initial)):
        for j in range(len(initial[0])): 
            to_change = final[i][j] - initial[i][j]
            if to_change < 0:  
                # check if there's a match if not store away
                for k in range(len(connect)): 
                    if connect[k][0] == i:
                        while connect[k][2] and abs(to_change):
                            connect[k][2] -= 1
                            to_change += 1
                            log.append([i, connect[k][1], i, j]) 
                    if not abs(to_change):
                        break
                if abs(to_change):
                    disconnect.append([i, j, to_change]) 
            elif to_change > 0:
                for k in range(len(disconnect)): 
                    if disconnect[k][0] == i:
                        while abs(disconnect[k][2]) and to_change:
                            disconnect[k][2] += 1
                            to_change -= 1
                            log.append([i, disconnect[k][1], i, j]) 
                    if not abs(to_change):
                        break 
                if abs(to_change):
                    connect.append([i, j, to_change])      
    return log
 
  def link_change_at(self, p, changes):
      print(p, changes)
      for i in range(len(changes)):
          if changes[i][1] == p:
              return changes[i], changes[:i]+changes[i+1:]
      print("No link to move from this spine block!")

  def swap(self, changes, capacity):
      actions = []
      s0, p0, _s1, p1 = changes.pop(0)
      actions.append(("DISCONNECT", s0, p0))
      if capacity[p1] == 0 and len(changes):
          tmp = self.link_change_at(p1, changes) 
          s2, p2, _s3, p3 = tmp[0]
          changes_p = tmp[1]
          actions.append(("DISCONNECT", s2, p2))
          actions.append(("CONNECT", s2, p0))
          changes = [(s2, p0, s2, p3)] + changes_p
      elif len(changes):
          capacity[p1] -= 1
          capacity[p0] += 1
      actions.append(("CONNECT", s0, p1))
      return actions, changes, capacity 
    
                


