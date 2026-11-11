# Experiment summary

- datapath: `user`, link delay emulated: `False`
- args: `{"scenarios": "b", "baseline": 30.0, "attack": 25, "recover": 45, "iperf_rate": "10M", "attack_size": 1000}`

| case | detect delay (s) | blocked | anomalous links | h1→h6 path before | during | after | Mbps b/d/a | loss % b/d/a | attack pkts at victim before block · pps after |
|---|---|---|---|---|---|---|---|---|---|
| b (h2→h6, s2-s6) | 1.5 | yes | s2-s6 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 10.50 / 10.30 / 10.50 | 0.00 / 1.85 / 0.00 | 3722 · 0.0 |

## Events (relative to baseline start)

| t (s) | event | src→dst | detail |
|---|---|---|---|
| 31.6 | block | h2→h6 | {"ip": "10.0.0.2", "pps": 886.1, "baseline": 0.96, "threshold": 500.0, "links": ["s2-s6"]} |
| 70.0 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.0} |

b/d/a = 15 s before the flood / during the flood / last 15 s of recovery.
Only h1→h6 reroutes are listed; all reroutes are in controller/events.csv.
