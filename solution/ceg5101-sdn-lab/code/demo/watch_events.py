#!/usr/bin/env python3
"""Pane: controller decisions as they happen (block, reroute, unblock, link changes)."""
import csv
import io
import json
import os
from _live import (BOLD, GREEN, GREY, ORANGE, RED, RESET, YELLOW, follow, out_dir_from_argv, phase, rel, t0)

out = out_dir_from_argv()
print(BOLD + 'CONTROLLER EVENTS' + RESET + GREY + '  (block / reroute h1->h6 / unblock)' + RESET, flush=True)
header = None
for line in follow(os.path.join(out, 'controller', 'events.csv')):
    if not line.strip():
        continue
    if header is None:
        header = next(csv.reader([line]))
        continue
    row = dict(zip(header, next(csv.reader(io.StringIO(line)))))
    ev, src, dst = row.get('event'), row.get('src'), row.get('dst')
    try:
        d = json.loads(row.get('detail') or '{}')
    except ValueError:
        d = {}
    t = rel(row['t'], t0(out))
    if ev == 'topology_ready':
        print(GREY + t + '  topology ready: %s switch links found' % d.get('detail_links') + RESET, flush=True)
    elif ev == 'block':
        print(RED + BOLD + t + '  BLOCK %s' % src + RESET + RED +
              '  %s pkt/s > threshold %s  -> drop rule on all switches' % (d.get('pps'), d.get('threshold')) + RESET)
        print(RED + '            links marked A=1: %s' % ', '.join(d.get('links', [])) + RESET, flush=True)
    elif ev == 'reroute' and src == 'h1' and dst == 'h6' and not (d.get('reason') == 'link_down' and phase(out) == 'finished'):
        print(ORANGE + BOLD + t + '  REROUTE h1->h6' + RESET + ORANGE +
              '  %s -> %s   (%s: stay %s vs move %s)' % (d.get('old'), d.get('new'), d.get('reason'),
                                                        d.get('old_cost'), d.get('new_cost')) + RESET, flush=True)
    elif ev == 'unblock':
        print(GREEN + BOLD + t + '  UNBLOCK %s' % src + RESET + GREEN +
              '  quiet for %s s' % d.get('quiet_s') + RESET, flush=True)
    elif ev in ('link_down', 'link_up') and phase(out) != 'finished':   # hide Mininet teardown
        print(YELLOW + t + '  %s %s' % (ev.upper(), ', '.join(d.get('detail_links', []))) + RESET, flush=True)
