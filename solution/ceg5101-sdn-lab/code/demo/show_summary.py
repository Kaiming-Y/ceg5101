#!/usr/bin/env python3
"""After a run: one compact table per case, computed from that run's own files."""
import csv
import json
import os
import re
import sys
from _live import BOLD, GREEN, GREY, ORANGE, RED, RESET, out_dir_from_argv

out = out_dir_from_argv()
tl = json.load(open(os.path.join(out, 'timeline.json'), encoding='utf-8'))
base = [m['t'] for m in tl['marks'] if m['name'] == 'baseline_start'][0]
iperf_start = [m['t'] for m in tl['marks'] if m['name'] == 'iperf_start'][0]
starts = {m['scenario']: m['t'] for m in tl['marks'] if m.get('scenario') and m['name'] == 'attack_start'}
ends = {m['scenario']: m['t'] for m in tl['marks'] if m.get('scenario') and m['name'] == 'attack_end'}
end_mark = next((m['t'] for m in tl['marks'] if m['name'] == 'end'), float('inf'))

events = list(csv.DictReader(open(os.path.join(out, 'controller', 'events.csv'), encoding='utf-8')))
secs = []
pat = re.compile(r'(\d+\.\d+)-\s*(\d+\.\d+)\s+sec.*?([\d.]+)\s+([KM]?)bits/sec.*?(\d+)/\s*(\d+)\s+\(([\d.]+)%\)')
for line in open(os.path.join(out, 'iperf_server.txt'), encoding='utf-8', errors='replace'):
    m = pat.search(line)
    if m and float(m.group(2)) - float(m.group(1)) <= 1.5:
        mbps = float(m.group(3)) / (1000.0 if m.group(4) == 'K' else 1.0)
        secs.append((iperf_start + float(m.group(2)), mbps, float(m.group(7))))

print(BOLD + '\nRESULT OF THIS RUN  (%s)' % out + RESET)
print(BOLD + '%-5s %-11s %-8s %-16s %-33s %-14s %s' % ('case', 'detected in', 'blocked', 'links marked A=1',
                                                      'h1->h6 rerouted', 'worst 1s loss', 'loss after block') + RESET)
for c in sorted(starts):
    s, e = starts[c], ends.get(c, starts[c] + 25)
    blk = [x for x in events if x['event'] == 'block' and s <= float(x['t']) <= e + 5]
    if blk:
        d = json.loads(blk[0]['detail'])
        det = '%.1f s' % (float(blk[0]['t']) - s)
        who = blk[0]['src']
        links = ', '.join(d.get('links', []))
        tb = float(blk[0]['t'])
    else:
        det, who, links, tb = 'NOT DETECTED', '-', '-', None
    limit = min([t for t in starts.values() if t > s] + [end_mark])       # until the next case / end of run
    rr = [x for x in events if x['event'] == 'reroute' and x['src'] == 'h1' and x['dst'] == 'h6'
          and s <= float(x['t']) < limit and json.loads(x['detail']).get('reason') != 'link_down']
    if rr:
        d0 = json.loads(rr[0]['detail'])
        moved = ORANGE + ('%-33s' % ('yes -> %s%s' % (d0.get('new'), '  (+ back)' if len(rr) > 1 else ''))) + RESET
    else:
        moved = '%-33s' % 'no'
    window = [x for x in secs if s < x[0] <= e + 1]
    worst = max((x[2] for x in window), default=0.0)
    after = [x[2] for x in window if tb and x[0] - 1 >= tb + 1]
    after_s = (GREEN + '0 %' + RESET) if after and max(after) == 0 else ('%.1f %%' % max(after) if after else '-')
    print('%-5s %-11s %-8s %-16s %s %-14s %s' % (c, det, who, links, moved, '%.1f %%' % worst, after_s))
normal = [x for x in secs if all(not (starts[c] - 1 < x[0] <= ends.get(c, starts[c] + 25) + 1) for c in starts)]
first = [x for x in normal if x[0] <= iperf_start + 2]          # first seconds: flow rules still being installed
rest = [x[2] for x in normal if x[0] > iperf_start + 2]
if rest:
    print(GREY + 'outside the floods: max loss %.1f %% over %d seconds' % (max(rest), len(rest)) +
          ('   (first 2 s of iperf, while the path is set up: %.1f %%)' % max(x[2] for x in first) if first else '') + RESET)
print(GREY + 'full table: %s/summary.md   figures: %s/figures/' % (out, out) + RESET)
