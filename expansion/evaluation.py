#!/usr/bin/env python

import collections
from collections import defaultdict
import os
import re
import shutil
import time
import sys
import commands
import math
import random
from utils import *

NUM_HOSTS=16

MN_PATH='~/mininet'
MN_UTIL=os.path.join(MN_PATH, 'util', 'm')

CmdTrafficGenClient = {
    'start': './tg_client -c {cdf_file} -s 16 -l logs/{host_name}.log 2>&1',
    'kill' : 'sudo pkill -9 "tg_client" 2>/dev/null'
}

CmdTrafficGenServer = {
    'start': './tg_server',
    'kill' : 'sudo pkill -9 "tg_server" 2>/dev/null'
}

CDF_FILE = None
CDF_REQ_NUM = {
    'SHORT_CDF' : 3800,
    'LONG_CDF' : 1500,
}

LOG_FOLDER_NAME = 'logs'
LOG_FORMAT = os.path.join(LOG_FOLDER_NAME, 'h%d.cdf')
TG_CLIENT_FLOW_FORMAT = os.path.join(LOG_FOLDER_NAME, 'h%d.log_flows.out')
TG_CLIENT_REQ_FORMAT = os.path.join(LOG_FOLDER_NAME, 'h%d.log_reqs.out')
TG_CLIENT_LOG_FORMAT = os.path.join(LOG_FOLDER_NAME, 'h%d.log')

NUM_BINS = 5
MTU = 1400
RTT = 30

def MnExec(hostName, command):
    cmd = '%s %s %s' % (MN_UTIL, hostName, command)
    return invoke('sh', '-c', cmd)

class Experiment:
    def __init__(self, nhost, duration):
        self.nhost = nhost
        self.duration = duration
    def start(self):

        print("Starting server processes")
        serv_procs = []
        for i in range(self.nhost):
            self.write_client_config(i+1)
            host = "h%d"%(i+1)
            serv_procs.append(self.run_tg_server(host))

        time.sleep(1)

        print("Starting client processes")
        clnt_procs = []
        for i in range(self.nhost):
            host = "h%d"%(i+1)
            clnt_procs.append(self.run_tg_client(host))

        print("Waiting for experiment to finish, up to %d seconds" % self.duration)
        monitor(clnt_procs, policy=all_exit, wait=self.duration)

        time.sleep(5)

        print("Stopping server and client processes")
        for i in range(self.nhost):
            host = "h%d"%(i+1)
            self.stop_tg_server(host)
            self.stop_tg_client(host)

        print("Cleaning up")
        self.clean_client_config()
        self.rename_tg_log()
        print("Experiment done")

    def run_tg_server(self, host):
        return MnExec(host, CmdTrafficGenServer["start"])
    def run_tg_client(self, host):
        return MnExec(host, CmdTrafficGenClient["start"].format(
            cdf_file=LOG_FORMAT % int(host[1:]),
            host_name = host))
    def stop_tg_server(self, host):
        return MnExec(host, CmdTrafficGenServer["kill"])
    def stop_tg_client(self, host):
        return MnExec(host, CmdTrafficGenClient["kill"])

    def clean_client_config(self):
        for i in range(NUM_HOSTS):
            fn = LOG_FORMAT % (i+1)
            if os.path.isfile(fn):
                os.remove(fn)

    def rename_tg_log(self):
        for i in range(NUM_HOSTS):
            req_fn = TG_CLIENT_REQ_FORMAT % (i+1)
            flow_fn = TG_CLIENT_FLOW_FORMAT % (i+1)
            log_fn = TG_CLIENT_LOG_FORMAT % (i+1)
            shutil.copy(flow_fn, log_fn)
            if os.path.isfile(req_fn):
                os.remove(req_fn)
            if os.path.isfile(flow_fn):
                os.remove(flow_fn)

    def write_client_config(self, host_id):
        fn = LOG_FORMAT % (host_id)
        with open(fn, 'w') as fp:
            for i in range(NUM_HOSTS):
                if (i+1+1) / 2 == (host_id+1) / 2:
                    continue
                fp.write("server 10.0.0.%d 5000\n" % (i+1))
            fp.write("req_size_dist %s\n" % CDF_FILE)
            fp.write("fanout 1 100\n")
            fp.write("load 7Mbps\n")
            fp.write("num_reqs %d\n" % CDF_REQ_NUM[CDF_FILE])

def average(l):
    return sum(l) * 1.0 / len(l)

def theo_fct(f_s):
    if f_s <= MTU:
        return RTT
    else:
        return f_s * 8 / 10

def calc_score():
    fcts = []
    for i in range(NUM_HOSTS):
        fp = TG_CLIENT_LOG_FORMAT % (i+1)
        with open(fp, 'r') as fp:
            for line in fp:
                f_s = int(line.split(', ')[0].split(':')[1])
                fct = int(line.split(', ')[1].split(':')[1])
                fcts.append((f_s, fct))

    min_fs = min([i[0] for i in fcts])
    max_fs = max([i[0] for i in fcts])
    bins = range(min_fs, max_fs, (max_fs - min_fs) / (NUM_BINS + 1))[:NUM_BINS]
    bins.append(max_fs + 1)

    for i in range(NUM_BINS):
        b_l = bins[i]
        b_r = bins[i+1]
        bin_fcts = [i for i in fcts if i[0] >= b_l and i[0] < b_r]
        yield average([i[1] * 1.0 / theo_fct(i[0]) for i in bin_fcts])

def read_score_config(score_file):
    with open(score_file, "r") as file:
        a,b = map(float, file.readlines())
    return a,b

def make_log_dir():
    if os.path.exists(LOG_FOLDER_NAME):
        shutil.rmtree(LOG_FOLDER_NAME)
    os.makedirs(LOG_FOLDER_NAME)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "usage: python evaluation.py <path to flow cdf>"
        exit(0)
    CDF_FILE = sys.argv[1]
    if CDF_FILE not in CDF_REQ_NUM:
        print "Please provide one of the following flow cdf files: %s" % \
                list(CDF_REQ_NUM.keys())
        exit(0)
    e = Experiment(16, 240)
    make_log_dir()
    e.start()
    print("=== Overall result ===")
    print(list(calc_score()))
