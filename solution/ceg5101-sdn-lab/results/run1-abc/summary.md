# Experiment summary

- datapath: `user`, link delay emulated: `False`
- args: `{"scenarios": "a,b,c", "baseline": 40, "attack": 25, "recover": 45, "iperf_rate": "10M", "attack_size": 1000}`

| case | detect delay (s) | blocked | anomalous links | h1→h6 path before | during | after | Mbps b/d/a | loss % b/d/a | attack pkts at victim before block · pps after |
|---|---|---|---|---|---|---|---|---|---|
| a (h2→h3, s2-s3) | 2.2 | yes | s2-s3 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 10.50 / 10.50 / 10.50 | 0.00 / 0.00 / 0.00 | 8131 · 0.0 |
| b (h2→h6, s2-s6) | 2.6 | yes | s2-s6 | s1-s2-s6 | s1-s2-s3-s6 (90%), s1-s2-s6 (9%) | s1-s2-s6 | 10.50 / 10.06 / 10.50 | 0.00 / 4.20 / 0.00 | 7841 · 0.0 |
| c (h5→h6, s5-s6) | 3.0 | yes | s3-s5, s3-s6 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 10.50 / 10.45 / 10.50 | 0.00 / 0.45 / 0.00 | 8780 · 0.0 |

## Events (relative to baseline start)

| t (s) | event | src→dst | detail |
|---|---|---|---|
| 42.3 | block | h2→h3 | {"ip": "10.0.0.2", "pps": 1893.4, "baseline": 0.98, "threshold": 500.0, "links": ["s2-s3"]} |
| 78.3 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.0} |
| 114.4 | block | h2→h6 | {"ip": "10.0.0.2", "pps": 3135.7, "baseline": 0.96, "threshold": 500.0, "links": ["s2-s6"]} |
| 114.4 | reroute | h1→h6 | {"reason": "anomaly", "old": "s1-s2-s6", "new": "s1-s2-s3-s6", "old_cost": 57.22, "new_cost": 30.1} |
| 150.4 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.0} |
| 150.4 | reroute | h1→h6 | {"reason": "cost_update", "old": "s1-s2-s3-s6", "new": "s1-s2-s6", "old_cost": 30.09, "new_cost": 24.5} |
| 186.5 | block | h5→h6 | {"ip": "10.0.0.5", "pps": 3889.3, "baseline": 1.04, "threshold": 500.0, "links": ["s3-s5", "s3-s6"]} |
| 222.5 | unblock | h5→· | {"ip": "10.0.0.5", "quiet_s": 12.0} |

b/d/a = 15 s before the flood / during the flood / last 15 s of recovery.
Only h1→h6 reroutes are listed; all reroutes are in controller/events.csv.
