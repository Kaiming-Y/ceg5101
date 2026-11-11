# Experiment summary

- datapath: `user`, link delay emulated: `False`
- args: `{"scenarios": "a,b,c", "baseline": 40, "attack": 25, "recover": 45, "iperf_rate": "10M", "attack_size": 1000}`

| case | detect delay (s) | blocked | anomalous links | h1→h6 path before | during | after | Mbps b/d/a | loss % b/d/a | attack pkts at victim before block · pps after |
|---|---|---|---|---|---|---|---|---|---|
| a (h2→h3, s2-s3) | 3.5 | yes | s2-s3 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 10.50 / 10.50 / 10.50 | 0.00 / 0.00 / 0.00 | 14251 · 0.0 |
| b (h2→h6, s2-s6) | 1.5 | yes | s2-s6 | s1-s2-s6 | s1-s2-s3-s6 (100%) | s1-s2-s6 | 10.50 / 10.30 / 10.50 | 0.00 / 1.87 / 0.00 | 3608 · 0.0 |
| c (h5→h6, s5-s6) | 1.8 | yes | s3-s5, s3-s6 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 10.50 / 10.47 / 10.50 | 0.00 / 0.31 / 0.00 | 4679 · 0.0 |

## Events (relative to baseline start)

| t (s) | event | src→dst | detail |
|---|---|---|---|
| 43.6 | block | h2→h3 | {"ip": "10.0.0.2", "pps": 4889.6, "baseline": 1.1, "threshold": 500.0, "links": ["s2-s3"]} |
| 79.6 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.0} |
| 113.2 | block | h2→h6 | {"ip": "10.0.0.2", "pps": 698.5, "baseline": 0.96, "threshold": 500.0, "links": ["s2-s6"]} |
| 113.2 | reroute | h1→h6 | {"reason": "anomaly", "old": "s1-s2-s6", "new": "s1-s2-s3-s6", "old_cost": 55.34, "new_cost": 30.22} |
| 151.7 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.0} |
| 151.7 | reroute | h1→h6 | {"reason": "cost_update", "old": "s1-s2-s3-s6", "new": "s1-s2-s6", "old_cost": 30.09, "new_cost": 24.17} |
| 185.3 | block | h5→h6 | {"ip": "10.0.0.5", "pps": 1425.6, "baseline": 1.03, "threshold": 500.0, "links": ["s3-s5", "s3-s6"]} |
| 223.8 | unblock | h5→· | {"ip": "10.0.0.5", "quiet_s": 12.0} |

b/d/a = 15 s before the flood / during the flood / last 15 s of recovery.
Only h1→h6 reroutes are listed; all reroutes are in controller/events.csv.
