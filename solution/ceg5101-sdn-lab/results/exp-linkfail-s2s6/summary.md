# Experiment summary

- datapath: `user`, link delay emulated: `False`
- args: `{"scenarios": "", "baseline": 30.0, "attack": 25, "recover": 30.0, "iperf_rate": "10M", "attack_size": 1000}`

| case | detect delay (s) | blocked | anomalous links | h1→h6 path before | during | after | Mbps b/d/a | loss % b/d/a | attack pkts at victim before block · pps after |
|---|---|---|---|---|---|---|---|---|---|

## Link failure: s2-s6

| h1→h6 path before | while down | after restore | Mbps b/d/a | loss % b/d/a |
|---|---|---|---|---|
| s1-s2-s6 | s1-s2-s3-s6 (100%) | s1-s2-s6 | 10.50 / 10.49 / 10.50 | 0.00 / 0.06 / 0.00 |

## Events (relative to baseline start)

| t (s) | event | src→dst | detail |
|---|---|---|---|
| 30.1 | link_down | →· | {"detail_links": ["s2-s6"]} |
| 30.1 | reroute | h1→h6 | {"reason": "link_down", "old": "s1-s2-s6", "new": "s1-s2-s3-s6", "old_cost": "inf", "new_cost": 30.21} |
| 50.8 | reroute | h1→h6 | {"reason": "cost_update", "old": "s1-s2-s3-s6", "new": "s1-s2-s6", "old_cost": 30.09, "new_cost": 25.47} |

b/d/a = 15 s before the flood / during the flood / last 15 s of recovery.
Only h1→h6 reroutes are listed; all reroutes are in controller/events.csv.
