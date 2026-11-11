#!/usr/bin/env python3
"""Pane: h1 -> h6 per-second throughput and loss, measured at the receiver h6 (iperf server)."""
import os
import re
from _live import BOLD, GREEN, GREY, RED, RESET, YELLOW, follow, out_dir_from_argv

out = out_dir_from_argv()
print(BOLD + 'h1 -> h6 AT THE RECEIVER' + RESET + GREY + '  (iperf, 10 Mbps UDP, one line per second)' + RESET,
      flush=True)
pat = re.compile(r'(\d+\.\d+)-\s*(\d+\.\d+)\s+sec.*?([\d.]+)\s+([KM]?)bits/sec.*?(\d+)/\s*(\d+)\s+\(([\d.]+)%\)')
for line in follow(os.path.join(out, 'iperf_server.txt')):
    m = pat.search(line)
    if not m or float(m.group(2)) - float(m.group(1)) > 1.5:      # skip the final summary line
        continue
    mbps = float(m.group(3)) / (1000.0 if m.group(4) == 'K' else 1.0)
    loss = float(m.group(7))
    bar = '#' * int(round(mbps * 2))
    colour = GREEN if loss == 0 else (YELLOW if loss < 5 else RED)
    lossbar = ('!' * min(30, int(round(loss / 2)))) if loss else ''
    print('%5.0f s  %s%5.2f Mbps %-21s%s  loss %s%5.1f %%%s %s' % (
        float(m.group(2)), colour, mbps, bar, RESET, colour, loss, RESET, RED + lossbar + RESET), flush=True)
