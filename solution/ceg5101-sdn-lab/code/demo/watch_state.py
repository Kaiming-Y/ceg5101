#!/usr/bin/env python3
"""Pane: a 1-second dashboard of the controller's state: phase, h1->h6 path, link costs, sources."""
import os
import time
from _live import (BLUE, BOLD, GREY, ORANGE, RED, RESET, last_rows, out_dir_from_argv, phase, t0)

out = out_dir_from_argv()
ctrl = os.path.join(out, 'controller')
LINKS = ['s1-s2', 's2-s6', 's2-s3', 's3-s6', 's3-s5', 's5-s6']
HOSTS = {'10.0.0.1': 'h1 (legit)', '10.0.0.2': 'h2', '10.0.0.5': 'h5'}

while True:
    lines = []
    base = t0(out)
    now = time.time()
    lines.append(BOLD + 'STATE' + RESET + GREY + '   t = %s' % ('%.0f s' % (now - base) if base else '-') + RESET)
    ph = phase(out, now)
    lines.append((RED + BOLD if ph.startswith('FLOOD') else BOLD) + ph + RESET)
    lines.append('')

    paths = [r for r in last_rows(os.path.join(ctrl, 'paths.csv')) if r.get('src') == 'h1' and r.get('dst') == 'h6']
    if paths:
        p = paths[-1]['path']
        main = p == 's1-s2-s6'
        lines.append('h1->h6 path: ' + (BLUE if main else ORANGE) + BOLD + p + RESET +
                     ('   (shortest, cost 19)' if main else '   (DETOUR)'))
    else:
        lines.append('h1->h6 path: -')
    lines.append('')

    rows = last_rows(os.path.join(ctrl, 'links.csv'))
    latest = {}
    for r in rows:
        latest[r['link']] = r
    lines.append(BOLD + 'link     C0   load Mbps   A   cost/C0' + RESET)
    for l in LINKS:
        r = latest.get(l)
        if not r:
            continue
        a = r['anomaly'] == '1'
        n = float(r['norm_cost'])
        bar = '=' * min(24, int(round(n * 4)))
        lines.append('%s%-7s %3s   %8.1f   %s   x%5.2f %s%s' % (
            RED if a else '', l, r['c0'], float(r['rate_mbps']), '1' if a else '0', n, bar, RESET))
    lines.append('')

    src = {}
    for r in last_rows(os.path.join(ctrl, 'sources.csv')):
        src[r['ip']] = r
    lines.append(BOLD + 'source         pkt/s   threshold   state' + RESET)
    for ip, name in HOSTS.items():
        r = src.get(ip)
        if not r:
            continue
        blocked = r['blocked'] == '1'
        lines.append('%s%-12s %8.0f   %9.0f   %s%s' % (
            RED + BOLD if blocked else '', name, float(r['pps']), float(r['threshold']),
            'BLOCKED' if blocked else 'ok', RESET))
    print('\033[H\033[2J' + '\n'.join(lines), flush=True)
    if ph == 'finished':
        break
    time.sleep(1)
