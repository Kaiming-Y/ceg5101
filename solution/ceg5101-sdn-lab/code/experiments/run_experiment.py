#!/usr/bin/env python3
"""
Automated experiment for CEG5101 CA2 (Task 4 + Task 5 data collection).

Timeline (one continuous run, so all cases appear on one time axis):
    baseline  : iperf UDP h1->h6 + 1 pps background pings (EMA baselines form)
    case a    : h2 -> h3 hping3 ICMP flood (loads s2-s3), then recovery
    case b    : h2 -> h6 flood (loads s2-s6, shares the h1->h6 path), then recovery
    case c    : h5 -> h6 flood (intended for s5-s6), then recovery

Usage (from the project root, as root):
    sudo python3 code/experiments/run_experiment.py --ryu-manager /path/to/ryu-manager
    sudo python3 code/experiments/run_experiment.py --scenarios b --attack 20
    sudo python3 code/experiments/run_experiment.py --controller external   # Ryu already running

Output: results/<timestamp>/  (controller CSVs, iperf/ping logs, flow dumps,
timeline.json) and, if matplotlib is available, figures/ + summary.md.
"""

import argparse
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from functools import partial

from mininet.clean import cleanup
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

CODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(CODE_DIR)

SCENARIOS = {
    'a': {'attacker': 'h2', 'victim': 'h3', 'link': 's2-s3'},
    'b': {'attacker': 'h2', 'victim': 'h6', 'link': 's2-s6'},
    'c': {'attacker': 'h5', 'victim': 'h6', 'link': 's5-s6'},
}
# Background 1 pps pings so every source has an EMA baseline before attacks.
BACKGROUND_PINGS = [('h2', 'h4'), ('h3', 'h5'), ('h4', 'h1'), ('h5', 'h2'), ('h6', 'h3')]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--scenarios', default='a,b,c', help='comma list from a,b,c (run in this order)')
    p.add_argument('--baseline', type=float, default=40, help='s of normal traffic before the first attack')
    p.add_argument('--attack', type=float, default=25, help='s each flood lasts')
    p.add_argument('--recover', type=float, default=45, help='s after each flood')
    p.add_argument('--iperf-rate', default='10M', help='h1->h6 UDP rate (iperf -b)')
    p.add_argument('--attack-size', type=int, default=1000, help='hping3 -d payload bytes')
    p.add_argument('--fail-link', default=None, metavar='sA-sB',
                   help='after the baseline, take this switch link down (resilience test), e.g. s2-s6')
    p.add_argument('--fail-for', type=float, default=20, help='s the failed link stays down')
    p.add_argument('--out', default=None, help='output dir (default results/<timestamp>)')
    p.add_argument('--controller', choices=['auto', 'external'], default='auto',
                   help='auto: start ryu-manager here; external: connect to a running one')
    p.add_argument('--ryu-manager', default=os.environ.get('RYU_MANAGER') or shutil.which('ryu-manager'),
                   help='ryu-manager executable (auto mode)')
    p.add_argument('--controller-ip', default='127.0.0.1')
    p.add_argument('--controller-port', type=int, default=6633)
    p.add_argument('--datapath', choices=['auto', 'kernel', 'user'], default='auto',
                   help='OVS datapath; user = userspace (containers without the OVS kernel module)')
    p.add_argument('--delay', choices=['auto', 'on', 'off'], default='auto',
                   help='keep TCLink delays (needs sch_netem); auto = on if available')
    p.add_argument('--plot-python', default=os.environ.get('PLOT_PYTHON', sys.executable),
                   help='python with matplotlib used for support/analysis/plot_results.py')
    p.add_argument('--cli', action='store_true', help='open the Mininet CLI before tearing down')
    return p.parse_args()


# ----------------------------------------------------------------------------
# Environment checks
# ----------------------------------------------------------------------------
def sh(cmd):
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)


def ensure_ovs():
    if sh('ovs-vsctl --timeout=3 show').returncode == 0:
        return
    info('*** Starting Open vSwitch\n')
    for cmd in ('service openvswitch-switch start',
                '/usr/share/openvswitch/scripts/ovs-ctl start --system-id=random'):
        sh(cmd)
        if sh('ovs-vsctl --timeout=3 show').returncode == 0:
            return
    sys.exit('Open vSwitch is not running and could not be started')


def detect_datapath(choice):
    if choice != 'auto':
        return choice
    return 'kernel' if os.path.exists('/sys/module/openvswitch') else 'user'


def netem_available():
    sh('ip link del cegt0')
    if sh('ip link add cegt0 type veth peer name cegt1').returncode != 0:
        return False
    ok = sh('tc qdisc add dev cegt0 root netem delay 1ms').returncode == 0
    sh('ip link del cegt0')
    return ok


def load_topology(with_delay):
    path = os.path.join(CODE_DIR, 'topology', 'ceg_mesh_topo.py')
    spec = importlib.util.spec_from_file_location('ceg_mesh_topo', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    topo = mod.MeshTopo()
    if not with_delay:
        # Link costs live in the controller, so routing is unaffected;
        # only absolute RTTs differ.
        for _, _, link_info in topo.links(withInfo=True):
            link_info.pop('delay', None)
    return topo


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
class Timeline(object):
    def __init__(self, path):
        self.path = path
        self.data = {'marks': [], 'scenarios': []}

    def mark(self, name, **kw):
        kw.update(name=name, t=time.time())
        self.data['marks'].append(kw)
        info('*** [%s] %s\n' % (time.strftime('%H:%M:%S'), name))
        self.save()

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)


def dump_flows(net, out_dir, label):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, label + '.txt'), 'w', encoding='utf-8') as f:
        for s in net.switches:
            f.write('===== %s =====\n' % s.name)
            f.write(s.cmd('ovs-ofctl -O OpenFlow13 dump-flows %s' % s.name))


def wait_topology(log_dir, timeout=90):
    path = os.path.join(log_dir, 'topology.json')
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(path, encoding='utf-8') as f:
                if json.load(f).get('ready'):
                    return True
        except (OSError, ValueError):
            pass
        time.sleep(1)
    return False


def iface_counter(host, counter):
    out = host.cmd('cat /sys/class/net/%s/statistics/%s' % (host.defaultIntf().name, counter))
    try:
        return int(out.strip())
    except ValueError:
        return -1


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    args = parse_args()
    if os.geteuid() != 0:
        sys.exit('Run as root (sudo): Mininet needs it')
    scenarios = [s.strip() for s in args.scenarios.split(',') if s.strip()]
    for s in scenarios:
        if s not in SCENARIOS:
            sys.exit('unknown scenario %r' % s)

    setLogLevel('info')
    out = os.path.abspath(args.out or os.path.join(ROOT, 'results', time.strftime('%Y%m%d-%H%M%S')))
    ctrl_dir = os.path.join(out, 'controller')
    os.makedirs(ctrl_dir, exist_ok=True)

    cleanup()
    ensure_ovs()
    datapath = detect_datapath(args.datapath)
    with_delay = netem_available() if args.delay == 'auto' else args.delay == 'on'
    meta = {'args': vars(args), 'datapath': datapath, 'delay_emulated': with_delay,
            'started': time.strftime('%Y-%m-%d %H:%M:%S %Z')}
    info('*** datapath=%s, link delay emulated=%s, output=%s\n' % (datapath, with_delay, out))
    if with_delay and not os.environ.get('CEG_WARMUP') and args.controller == 'auto':
        # With real link delays pingAll takes several seconds, so h1's iperf can start after a
        # 5-sample warm-up has ended; its ~900 pkt/s is then flagged and h1 gets blocked
        # (observed on the Mininet 2.3.0 VM). A longer warm-up lets the detector learn h1 first.
        os.environ['CEG_WARMUP'] = '12'
        info('*** link delays on: using CEG_WARMUP=12 (set CEG_WARMUP to override)\n')
    if args.controller == 'auto':      # what the controller started below receives
        meta['ceg_env_passed_to_controller'] = {k: v for k, v in os.environ.items() if k.startswith('CEG_')}
    # in every mode the controller itself records its parameters in <out>/controller/config.json

    ryu = None
    if args.controller == 'auto':
        if not args.ryu_manager:
            sys.exit('ryu-manager not found: pass --ryu-manager or use --controller external')
        env = dict(os.environ, CEG_LOG_DIR=ctrl_dir)
        ryu_log = open(os.path.join(out, 'ryu.log'), 'w', encoding='utf-8')
        ryu = subprocess.Popen(
            [args.ryu_manager, '--observe-links', '--ofp-tcp-listen-port', str(args.controller_port),
             os.path.join(CODE_DIR, 'controller', 'integrated_controller.py')],
            stdout=ryu_log, stderr=subprocess.STDOUT, cwd=ROOT, env=env, start_new_session=True)
        time.sleep(4)
        if ryu.poll() is not None:
            sys.exit('ryu-manager exited early, see %s/ryu.log' % out)
    else:
        info('*** Using external controller; its CEG_LOG_DIR should be %s\n' % ctrl_dir)

    net = Mininet(topo=load_topology(with_delay),
                  switch=partial(OVSSwitch, protocols='OpenFlow13', datapath=datapath),
                  link=TCLink, controller=None, autoSetMacs=True, build=False)
    net.addController('c0', controller=RemoteController, ip=args.controller_ip, port=args.controller_port)
    timeline = Timeline(os.path.join(out, 'timeline.json'))
    procs_started = False
    try:
        net.build()
        net.start()
        # IPv6 chatter and NIC offloads only add noise (offloads also break
        # the userspace datapath's checksums).
        has_ethtool = shutil.which('ethtool') is not None
        for h in net.hosts:
            h.cmd('sysctl -qw net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1')
        for node in net.hosts + net.switches:
            for intf in node.intfList():
                if intf.name == 'lo':
                    continue
                if node in net.switches:
                    node.cmd('sysctl -qw net.ipv6.conf.%s.disable_ipv6=1' % intf.name)
                if has_ethtool:
                    node.cmd('ethtool -K %s tx off rx off tso off gso off gro off >/dev/null 2>&1' % intf.name)

        info('*** Waiting for the controller to discover all links\n')
        if not wait_topology(ctrl_dir):
            info('!!! topology not ready after timeout - continuing anyway\n')
        timeline.mark('topology_ready')
        meta['pingall_loss_pct'] = [net.pingAll(timeout='1'), net.pingAll(timeout='1')]

        h1, h6 = net.get('h1', 'h6')
        total = args.baseline + len(scenarios) * (args.attack + args.recover) + 5
        if args.fail_link:
            total += args.fail_for + args.recover
        procs_started = True
        h6.cmd('stdbuf -oL iperf -s -u -i 1 -e > %s/iperf_server.txt 2>&1 &' % out)   # line-buffered: live viewing
        time.sleep(1)
        timeline.mark('iperf_start')
        h1.cmd('iperf -c %s -u -b %s -t %d -i 1 > %s/iperf_client.txt 2>&1 &'
               % (h6.IP(), args.iperf_rate, total, out))
        h1.cmd('ping -D -i 0.5 %s > %s/ping_h1_h6.txt 2>&1 &' % (h6.IP(), out))
        for src, dst in BACKGROUND_PINGS:
            net.get(src).cmd('ping -i 1 %s > /dev/null 2>&1 &' % net.get(dst).IP())

        timeline.mark('baseline_start')
        time.sleep(args.baseline)
        dump_flows(net, os.path.join(out, 'flows'), '00_baseline')

        if args.fail_link:
            a, b = args.fail_link.split('-')
            timeline.mark('link_down', link=args.fail_link)
            net.configLinkStatus(a, b, 'down')
            time.sleep(args.fail_for / 2)
            dump_flows(net, os.path.join(out, 'flows'), '00_link_down')
            time.sleep(args.fail_for / 2)
            net.configLinkStatus(a, b, 'up')
            timeline.mark('link_up', link=args.fail_link)
            time.sleep(args.recover)
            dump_flows(net, os.path.join(out, 'flows'), '00_link_restored')

        rx_log = open(os.path.join(out, 'attack_counters.csv'), 'w', encoding='utf-8')
        rx_log.write('t,scenario,victim_rx_packets,attacker_tx_packets\n')
        for idx, sid in enumerate(scenarios, 1):
            sc = SCENARIOS[sid]
            attacker, victim = net.get(sc['attacker']), net.get(sc['victim'])
            entry = dict(sc, id=sid)
            entry['attack_start'] = time.time()
            timeline.mark('attack_start', scenario=sid)
            # Count only the attacker's packets that actually reach the victim.
            victim.cmd('tcpdump -i %s -n -tt -q -l "icmp and src host %s" > %s/victim_capture_%s.txt 2>/dev/null &'
                       % (victim.defaultIntf().name, attacker.IP(), out, sid))
            time.sleep(0.5)
            attacker.cmd('timeout -s INT %d hping3 --icmp --flood -d %d %s > %s/hping3_%s.txt 2>&1 &'
                         % (args.attack, args.attack_size, victim.IP(), out, sid))
            t_end = time.time() + args.attack
            dumped = False
            while time.time() < t_end:
                rx_log.write('%.3f,%s,%d,%d\n' % (time.time(), sid, iface_counter(victim, 'rx_packets'),
                                                   iface_counter(attacker, 'tx_packets')))
                rx_log.flush()
                if not dumped and time.time() > entry['attack_start'] + min(10, args.attack / 2):
                    dump_flows(net, os.path.join(out, 'flows'), '%02d_%s_during' % (idx, sid))
                    dumped = True
                time.sleep(1)
            attacker.cmd('pkill -INT -f "hping3 --icmp" 2>/dev/null')
            entry['attack_end'] = time.time()
            time.sleep(1)
            victim.cmd('pkill -INT tcpdump')
            timeline.mark('attack_end', scenario=sid)
            time.sleep(args.recover)
            entry['recover_end'] = time.time()
            dump_flows(net, os.path.join(out, 'flows'), '%02d_%s_after' % (idx, sid))
            timeline.data['scenarios'].append(entry)
            timeline.save()
        rx_log.close()
        timeline.mark('end')

        if args.cli:
            CLI(net)
    finally:
        if procs_started:
            for n in net.hosts:
                n.cmd('pkill -INT iperf; pkill -INT ping; pkill -INT hping3; pkill -INT tcpdump')
            time.sleep(2)
        net.stop()
        if ryu is not None:
            try:
                os.killpg(ryu.pid, signal.SIGINT)
                ryu.wait(timeout=10)
            except Exception:
                os.killpg(ryu.pid, signal.SIGKILL)
        meta['finished'] = time.strftime('%Y-%m-%d %H:%M:%S %Z')
        with open(os.path.join(out, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
        # Files were created as root; hand them back to the invoking user.
        if os.environ.get('SUDO_UID'):
            sh('chown -R %s:%s "%s"' % (os.environ['SUDO_UID'], os.environ.get('SUDO_GID', ''), out))

    plot = os.path.join(ROOT, 'support', 'analysis', 'plot_results.py')
    r = subprocess.run([args.plot_python, plot, out])
    if r.returncode != 0:
        info('*** Plotting skipped/failed; run:  python3 support/analysis/plot_results.py %s\n' % out)
    info('*** Results in %s\n' % out)


if __name__ == '__main__':
    main()
