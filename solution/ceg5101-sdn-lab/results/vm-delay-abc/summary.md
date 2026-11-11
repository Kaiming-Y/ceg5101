# Experiment summary

- datapath: `kernel`, link delay emulated: `True`
- args: `{"scenarios": "a,b,c", "baseline": 40, "attack": 25, "recover": 45, "iperf_rate": "10M", "attack_size": 1000}`

| case | detect delay (s) | blocked | anomalous links | h1→h6 path before | during | after | Mbps b/d/a | loss % b/d/a | attack pkts at victim before block · pps after |
|---|---|---|---|---|---|---|---|---|---|
| a (h2→h3, s2-s3) | 2.2 | yes | s2-s3 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 10.50 / 10.48 / 10.50 | 0.00 / 0.00 / 0.00 | 4682 · 0.0 |
| b (h2→h6, s2-s6) | 1.6 | yes | s2-s6 | s1-s2-s6 | s1-s2-s3-s6 (100%) | s1-s2-s6 | 10.49 / 10.47 / 10.49 | 0.00 / 0.45 / 0.02 | 2171 · 0.0 |
| c (h5→h6, s5-s6) | 3.8 | yes | s3-s5, s3-s6 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 10.49 / 10.42 / 10.50 | 0.02 / 0.66 / 0.00 | 7677 · 0.0 |

## Events (relative to baseline start)

| t (s) | event | src→dst | detail |
|---|---|---|---|
| 43.3 | block | h2→h3 | {"ip": "10.0.0.2", "pps": 1355.2, "baseline": 1.05, "threshold": 500.0, "links": ["s2-s3"]} |
| 80.2 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.2} |
| 116.9 | block | h2→h6 | {"ip": "10.0.0.2", "pps": 635.1, "baseline": 1.1, "threshold": 500.0, "links": ["s2-s6"]} |
| 116.9 | reroute | h1→h6 | {"reason": "anomaly", "old": "s1-s2-s6", "new": "s1-s2-s3-s6", "old_cost": 54.96, "new_cost": 30.2} |
| 156.1 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.2} |
| 156.1 | reroute | h1→h6 | {"reason": "cost_update", "old": "s1-s2-s3-s6", "new": "s1-s2-s6", "old_cost": 30.08, "new_cost": 24.32} |
| 192.8 | block | h5→h6 | {"ip": "10.0.0.5", "pps": 3092.0, "baseline": 11.91, "threshold": 500.0, "links": ["s3-s5", "s3-s6"]} |
| 229.4 | unblock | h5→· | {"ip": "10.0.0.5", "quiet_s": 12.1} |

b/d/a = 15 s before the flood / during the flood / last 15 s of recovery.
Only h1→h6 reroutes are listed; all reroutes are in controller/events.csv.
