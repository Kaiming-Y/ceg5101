#!/usr/bin/env python3
"""Generate support/miniedit/ceg_mesh_topo.mn from code/topology/ceg_mesh_topo.py so the
MiniEdit canvas matches the Python topology exactly (names, dpids, IPs,
bw/delay on every link, remote controller c0).

    python3 support/miniedit/make_mn.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TOPO = os.path.join(HERE, '..', '..', 'code', 'topology', 'ceg_mesh_topo.py')

# Canvas layout: switches in two rows (s1 s2 s3 / s4 s5 s6), each host next to its switch.
SWITCH_XY = {1: (250, 220), 2: (450, 220), 3: (650, 220), 4: (250, 420), 5: (450, 420), 6: (650, 420)}
HOST_XY = {1: (250, 100), 2: (450, 100), 3: (650, 100), 4: (250, 540), 5: (450, 540), 6: (650, 540)}


def main():
    src = open(TOPO, encoding='utf-8').read()
    links = re.findall(r"addLink\(\s*(\w+),\s*(\w+),\s*cls=TCLink,\s*bw=(\d+),\s*delay='([^']+)'", src)
    topo = {
        'version': '2',
        'controllers': [{'x': '80', 'y': '320', 'opts': {
            'controllerType': 'remote', 'hostname': 'c0', 'remoteIP': '127.0.0.1',
            'remotePort': 6633, 'controllerProtocol': 'tcp'}}],
        'switches': [{'number': str(i), 'x': str(x), 'y': str(y), 'opts': {
            'hostname': 's%d' % i, 'nodeNum': i, 'switchType': 'default',
            'controllers': ['c0'], 'dpid': '%016x' % i}} for i, (x, y) in sorted(SWITCH_XY.items())],
        'hosts': [{'number': str(i), 'x': str(x), 'y': str(y), 'opts': {
            'hostname': 'h%d' % i, 'nodeNum': i, 'sched': 'host', 'ip': '10.0.0.%d/24' % i}}
            for i, (x, y) in sorted(HOST_XY.items())],
        'links': [{'src': a, 'dest': b, 'opts': {'bw': int(bw), 'delay': d}} for a, b, bw, d in links],
        # 'application' (preferences) is deliberately omitted: some Python 3
        # MiniEdit builds crash while merging it. Set OpenFlow 1.3 in
        # Edit -> Preferences instead (see PLAN.md, Phase 1).
    }
    assert len(topo['links']) == 17, 'expected 6 host links + 11 switch links, got %d' % len(topo['links'])
    out = os.path.join(HERE, 'ceg_mesh_topo.mn')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(topo, f, indent=4, sort_keys=True)
    print('wrote', out, '(%d links)' % len(topo['links']))


if __name__ == '__main__':
    main()
