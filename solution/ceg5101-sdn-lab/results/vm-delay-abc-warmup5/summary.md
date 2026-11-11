# Experiment summary

- datapath: `kernel`, link delay emulated: `True`
- args: `{"scenarios": "a,b,c", "baseline": 40, "attack": 25, "recover": 45, "iperf_rate": "10M", "attack_size": 1000}`

| case | detect delay (s) | blocked | anomalous links | h1→h6 path before | during | after | Mbps b/d/a | loss % b/d/a | attack pkts at victim before block · pps after |
|---|---|---|---|---|---|---|---|---|---|
| a (h2→h3, s2-s3) | 2.3 | yes | s2-s3 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 0.00 / 0.00 / 0.00 | 100.00 / 100.00 / 100.00 | 5257 · 0.0 |
| b (h2→h6, s2-s6) | 2.0 | yes | s2-s3, s3-s6 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 0.00 / 0.00 / 0.00 | 100.00 / 100.00 / 100.00 | 3454 · 0.0 |
| c (h5→h6, s5-s6) | 1.9 | yes | s3-s5, s3-s6 | s1-s2-s6 | s1-s2-s6 (100%) | s1-s2-s6 | 0.00 / 0.00 / 0.00 | 100.00 / 100.00 / 100.00 | 3560 · 0.0 |

## Events (relative to baseline start)

| t (s) | event | src→dst | detail |
|---|---|---|---|
| 4.3 | block | h1→h6 | {"ip": "10.0.0.1", "pps": 919.9, "baseline": 113.36, "threshold": 803.87, "links": ["s1-s2", "s2-s6"]} |
| 43.4 | block | h2→h3 | {"ip": "10.0.0.2", "pps": 1172.5, "baseline": 0.94, "threshold": 500.0, "links": ["s2-s3"]} |
| 80.0 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.1} |
| 116.6 | block | h2→h6 | {"ip": "10.0.0.2", "pps": 605.1, "baseline": 0.99, "threshold": 500.0, "links": ["s2-s3", "s3-s6"]} |
| 153.4 | unblock | h2→· | {"ip": "10.0.0.2", "quiet_s": 12.2} |
| 190.1 | block | h5→h6 | {"ip": "10.0.0.5", "pps": 583.3, "baseline": 1.06, "threshold": 500.0, "links": ["s3-s5", "s3-s6"]} |
| 226.7 | unblock | h5→· | {"ip": "10.0.0.5", "quiet_s": 12.2} |

b/d/a = 15 s before the flood / during the flood / last 15 s of recovery.
Only h1→h6 reroutes are listed; all reroutes are in controller/events.csv.
