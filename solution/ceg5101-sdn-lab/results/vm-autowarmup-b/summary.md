# Experiment summary

- datapath: `kernel`, link delay emulated: `True`
- args: `{"scenarios": "b", "baseline": 30.0, "attack": 25, "recover": 45, "iperf_rate": "10M", "attack_size": 1000}`

| case | detect delay (s) | blocked | anomalous links | h1→h6 path before | during | after | Mbps b/d/a | loss % b/d/a | attack pkts at victim before block · pps after |
|---|---|---|---|---|---|---|---|---|---|
| b (h2→h6, s2-s6) | 3.2 | yes | s2-s6 | s1-s2-s6 | s1-s2-s3-s6 (90%), s1-s2-s6 (9%) | s1-s2-s6 | 10.49 / 10.39 / 10.50 | 0.00 / 0.91 / 0.00 | 6930 · 0.0 |

## Events (relative to baseline start)

| t (s) | event | src→dst | detail |
|---|---|---|---|
| 34.6 | block | h2→h6 | {"ip": "10.0.0.2", "pps": 2757.9, "baseline": 1.04, "threshold": 500.0, "links": ["s2-s6"]} |
| 34.6 | reroute | h1→h6 | {"reason": "anomaly", "old": "s1-s2-s6", "new": "s1-s2-s3-s6", "old_cost": 57.04, "new_cost": 30.21} |
| 71.2 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.2} |
| 71.3 | reroute | h1→h6 | {"reason": "cost_update", "old": "s1-s2-s3-s6", "new": "s1-s2-s6", "old_cost": 30.09, "new_cost": 24.15} |

b/d/a = 15 s before the flood / during the flood / last 15 s of recovery.
Only h1→h6 reroutes are listed; all reroutes are in controller/events.csv.
