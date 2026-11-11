# Numbers used on the slides and in the speaker notes

Every value below was recomputed from the raw result files, not copied from the report. Where the report
rounds differently, both are given and the slide value is marked.

## Conventions

- **Runs.** R1 = `results/validation-abc`, R2 = `results/run1-abc`, R3 = `results/run2-abc`
  (container, userspace OVS, no link delay). VM = `results/vm-delay-abc` (Mininet 2.3.0 VM, kernel OVS,
  netem link delays, 12 warm-up samples).
- **Time axis.** Seconds since the `baseline_start` mark in `timeline.json` (R1: epoch 1792669980.032).
  R1 flood windows: a 40.1–65.7 s, b 111.8–137.5 s, c 183.5–209.2 s.
- **Flood start / end.** `attack_start` / `attack_end` of each entry in `timeline.json` → `scenarios`.
  The separate `attack_end` mark is about 1 s later (time the flood process exited) and is not used.
- **Per-second loss and throughput.** 1 s rows of `iperf_server.txt` (h6, `iperf -s -u -i 1 -e`), placed
  on the time axis by the server's connection timestamp; loss = Lost/Total of that second. A row is
  plotted over its own 1 s interval (e.g. the row ending at 113.0 s covers 112–113 s).
- **Flood window statistics** use the rows whose interval ends inside [flood start, flood end).
- **Detection delay** = time of the `block` event in `controller/events.csv` − flood start.
- **Link cost** from `controller/links.csv` (`norm_cost` = C/C0; `rate_mbps`, `anomaly`, `cost`).
- C0 (ms): s1-s2 5, s2-s3 10, s2-s6 14, s3-s5 9, s3-s6 7, s5-s6 20. Paths: s1-s2-s6 = 19, s1-s2-s3-s6 = 22,
  s5-s3-s6 = 16 < s5-s6 = 20.

## Detection and blocking (Task 2)

| Value | Meaning | Run | Source | How computed |
|---|---|---|---|---|
| a 3.4 / 2.2 / 3.5 s | detection delay, case a | R1 / R2 / R3 | `events.csv`, `timeline.json` | block − flood start: 3.402 / 2.226 / 3.501 |
| b 3.8 / 2.6 / 1.5 s | detection delay, case b | R1 / R2 / R3 | same | 3.757 / 2.591 / 1.467 |
| c 1.7 / 3.0 / 1.8 s | detection delay, case c | R1 / R2 / R3 | same | 1.711 / 2.974 / 1.830 |
| 1.5–3.8 s | detection range, all nine container floods | R1–R3 | same | min 1.467, max 3.757 |
| a 2.2 / b 1.6 / c 3.8 s | detection delay on the VM | VM | `vm-delay-abc/controller/events.csv` | 2.172 / 1.586 / 3.848 |
| 2.4 s | time between two detector samples | R1–R3 (VM 2.43 s) | `controller/sources.csv` | median gap between sample timestamps 2.402–2.403 s (2 s poll + fixed wait) |
| 0.5 s | flood starts after the timing mark | R1 | `victim_capture_*.txt` | first captured attack packet 0.51–0.53 s after flood start |
| 491 pkt/s | first (partial) h2 sample in case b, below the 500 floor, learned | R1 | `sources.csv`, 10.0.0.2 at t = 113.2 s | row value 490.7 |
| 1 → 148 pkt/s | h2 baseline before / after learning that sample | R1 | `sources.csv` | 0.97 at 110.8 s, 147.89 at 113.2 s |
| T = 500 → 1,046 pkt/s | h2 threshold before / after | R1 | `sources.csv` | 500.0 → 1045.61 |
| 4,994 pkt/s | sample that triggered the block at 115.6 s | R1 | `sources.csv`, `events.csv` | 4993.7 (block event detail) |
| 115.6 s | h2 blocked and h1→h6 rerouted in case b | R1 | `events.csv` | block 115.557, reroute 115.558 |
| ≈4,700–4,800 pkt/s | flood rate leaving the attacker (≈39 Mbps, 1,028-byte IP packets) | R1–R3 | `attack_counters.csv` (`attacker_tx_packets`) | counter slope from flood start to the block: 4,680–4,784 pkt/s; report rounds to "about 4,800" |
| 3,608–14,251 | attack packets reaching the victim before the block | R1–R3 | `victim_capture_*.txt` | count of captured packets with timestamp < block; R1 13,779 / 11,678 / 4,242, R2 8,131 / 7,841 / 8,780, R3 14,251 / 3,608 / 4,679 |
| 19–101 within ≤ 28 ms | packets already in flight that still arrived after the block | R1–R3 | same | captured packets in [block, block + 1 s): 19–101; the last one 5.8–28.5 ms after the block |
| 0 | attack packets reaching the victim later than 1 s after the block | all nine floods (and VM) | same | count with timestamp ≥ block + 1 s |
| 487–1,188 within ≤ 0.53 s | in-flight packets after the block on the VM (netem queues) | VM | `vm-delay-abc/victim_capture_*.txt` | same method; last one 158 / 176 / 525 ms after the block |
| 31,253 | `n_packets` of the priority-5000 drop rule on s2, 6.8 s after the block | R1 case b | `flows/02_b_during.txt` | value in the dump |
| s2-s3 / s2-s6 / s3-s5 + s3-s6 | links marked anomalous (A = 1) | R1–R3, VM | `events.csv` block detail `links` | same in all runs |

## Loss and throughput of h1→h6 (Task 5)

| Value | Meaning | Run | Source | How computed |
|---|---|---|---|---|
| 24 / 47 / 48 / 27 % | per-second loss in the four lossy seconds of case b (112–113 … 115–116 s) | R1 | `iperf_server.txt` | 24.2 / 47.3 / 48.4 / 27.4 % |
| 48.4 / 56.6 / 34.4 % | worst 1 s loss, case b | R1 / R2 / R3 | same | max over flood window |
| 2.5 / 4.1 / 6.1 % | worst 1 s loss, case c (h6 access link) | R1 / R2 / R3 | same | max over flood window |
| 0 % | loss in case a, and after every block | R1–R3 | same | all rows 0 in case a; 0 in every row ending ≥ 1 s after a block |
| 5.67 / 4.20 / 1.87 % | mean loss over the 25 s flood, case b | R1 / R2 / R3 | same | mean of per-second loss in the flood window |
| 0.12 / 0.45 / 0.31 % | mean loss over the flood, case c | R1 / R2 / R3 | same | same |
| 5.41 / 4.55 / 6.74 Mbps | lowest 1 s throughput, case b | R1 / R2 / R3 | same | min over flood window |
| 10.0 / 9.88 / 9.65 Mbps | lowest 1 s throughput, case c | R1 / R2 / R3 | same | min over flood window |
| 10.5 Mbps | throughput outside the lossy seconds (10 Mbps payload + headers) | R1–R3 | same | every 1 s row before each flood and in recovery |
| ≈890 pkt/s | h1's iperf packet rate | R1–R3 | `iperf_server.txt` | median 892 datagrams per 1 s row (whole-run average 886–890). The controller's own per-sample estimate in `sources.csv` alternates 745 / 931 pkt/s (median 931) |
| 0.5 → 20.5 ms | h1→h6 RTT, normal vs worst before the case b block | R1 | `ping_h1_h6.txt` | median before the first flood 0.50 ms; max between flood start and block + 1 s 20.5 ms |
| 99.8 / 109.0 / 100.0 ms | median RTT: before the first flood / on the detour / after the return | VM | `vm-delay-abc/ping_h1_h6.txt` | medians over [start, flood a), [reroute + 1 s, return), [return + 1 s, flood c); 107.0 ms on the detour after the flood ended; 98 ms expected = 2 × (15 + 5 + 14 + 15) |
| 383 ms | max RTT before the case b block on the VM (deep netem queue) | VM | same | max between flood start and block + 1 s |

## Link cost (Task 3) and rerouting (Task 4)

| Value | Meaning | Run | Source | How computed |
|---|---|---|---|---|
| ×1.19 | s2-s6 before the flood (carries h1→h6) | R1 | `links.csv`, s2-s6 | 1.1926 = (14 + 10 × 10.79/40)/14. The report text says "about 1.18"; slides use 1.19 |
| ×3.67 | s2-s6 at the block (load still present + β) | R1 | same, t = 115.6 s | 3.6713 = (14 + 10 × 29.59/40 + 30)/14 |
| ×3.14 | s2-s6 plateau while A = 1 and the load is gone | R1–R3, VM | same | 3.1429 = (14 + 30)/14, reached from about 137 s |
| ×1.0 | s2-s6 when A returns to 0 (h1 still on the detour) | R1 | same, t = 151.6 s | 1.000; rises back to ×1.19 within about 10 s once h1 returns |
| 4.0 / 3.14 / 4.33 / 5.29 | plateau (C0 + 30)/C0 of s2-s3 (a), s2-s6 (b), s3-s5 and s3-s6 (c) | R1–R3, VM | `links.csv` | minimum C/C0 while A = 1 and rate < 0.5 Mbps: 4.000 / 3.143 / 4.333 / 5.286 in every run |
| 4.3–4.6 (s2-s3), 3.4–3.7 (s2-s6) | spike at detection | R1–R3 | same | max C/C0 per case; s2-s3 4.32–4.62, s2-s6 3.41–3.67, s3-s5 4.54–4.87, s3-s6 5.51–5.85 |
| ×1.54 | s1-s2 throughout (carries h1→h6) | R1–R3 | same | 1.539 = (5 + 10 × 10.77/40)/5; h1's flow adds 2.7 to C0 = 5 |
| 1.27 / 1.39 | s2-s3 / s3-s6 while h1→h6 is on the detour | R1–R3 | same | max C/C0 between block and return |
| 1.0 | s5-s6 for the whole run (no flow uses it) | R1–R3 | same | max 1.002 |
| 58.78 vs 29.97 | path cost: stay on s1-s2-s6 vs move to s1-s2-s3-s6, at the block | R1 | `events.csv` reroute h1→h6 at 115.6 s | `old_cost` / `new_cost` |
| 30.09 vs 24.5 | path cost at the return: detour vs original | R1 | reroute h1→h6 at 151.6 s | `old_cost` / `new_cost` (R2 30.09/24.5, R3 30.09/24.17, VM 30.08/24.32) |
| 57.22 / 30.10, 55.34 / 30.22, 54.96 / 30.20 | stay vs move at the block | R2, R3, VM | same | `old_cost` / `new_cost` |
| 2 | h1→h6 reroutes per case b (away and back), none in a or c | R1–R3, VM | `events.csv` | count of h1→h6 reroute events before the `end` mark |
| 151.6 s | h1→h6 back on s1-s2-s6 | R1 | `events.csv` | second reroute |
| 39.8 / 38.6 / 39.9 s | return after flood start, case b | R1 / R2 / R3 | `events.csv`, `timeline.json` | return − flood start (VM 40.8 s) |
| 14.8 / 13.6 / 14.9 s | return after the nominal flood end (start + 25 s); report's "13.6–14.9 s" | R1 / R2 / R3 | same | VM 15.8 s |
| 14.1 / 13.0 / 14.3 s | return after the recorded flood end (`attack_end` in `scenarios`) | R1 / R2 / R3 | same | VM 14.8 s. Slide wording: "back ≈ 14 s after the flood" |
| 13.3–15.3 s | every marked link back to its baseline cost after the flood (10 s hold + 1–2 samples) | R1–R3 | `links.csv` | first sample with A = 0 after the flood − (flood start + 25 s) |
| β > 3.2 / 4.9 / 6.9 | β needed to move h1→h6 at the moment of the block | R1 / R2 / R3 (VM 7.2) | reroute `old_cost`, `new_cost` | stay cost without β = old_cost − 30; need (old_cost − 30) + β − new_cost > 2: 3.19 / 4.88 / 6.88 / 7.24 |
| β > ≈7.7 | β needed with no flood load left on s2-s6 | model | Eq. (1), `links.csv` rates | detour +3, h1's own load ≈2.7 added on two new links but already on s2-s6 (net +2.7), margin 2: 3 + 2.7 + 2 = 7.7 |
| 5 | β needed from static costs alone | model | C0 | 22 − 19 + margin 2 |

## Extended experiments

| Value | Meaning | Run | Source | How computed |
|---|---|---|---|---|
| β = 0: 1.20×, stayed, 30.4 %, 0 % | s2-s6 cost after the block, h1→h6 path, worst 1 s loss, loss after the block | `exp-beta0-b` | `links.csv`, `events.csv`, `iperf_server.txt` | cost: mean C/C0 from 3 s after the block to flood end (1.199; median 1.19, converges to 1.193 = h1's own load only); no h1→h6 reroute; detection 1.5 s |
| β = 2: 1.34×, stayed, 30.1 %, 0 % | same | `exp-beta2-b` | same | mean 1.342 (median 1.34, converges to 1.335) |
| β = 30: 3.15–3.16×, moved, 34.4–56.6 %, 0 % | same | R1–R3 | same | mean from 3 s after the block 3.156–3.167 (median 3.15), converges to 3.143 |
| C0 = 8, 1.5 s, 4.76×, 35 %, stayed | case c with s5-s6 forced: detection, s5-s6 cost during the flood, worst 1 s loss, h1→h6 path | `exp-c-s5s6-cost8` | same | marked link s5-s6 only; mean from 3 s after the block 4.763 (median 4.75, converges to (8 + 30)/8 = 4.75); worst second 35.2 %; no h1→h6 reroute |
| 7 ms | s2-s6 down → h1→h6 on s1-s2-s3-s6 | `exp-linkfail-s2s6` | `timeline.json` `link_down`, `events.csv` | reroute 7.3 ms after the `link_down` mark (2.0 ms after the controller's own link-down event) |
| 0.7 s | link restored → back on s1-s2-s6 | same | `link_up` mark, `events.csv` | 50.818 − 50.126 = 0.69 s |
| 11 / 71,515 | packets lost in the whole 80 s run, all in the second of the failure | same | `iperf_server.txt` final line | 11/71515 (0.015 %); the only lossy row is 30–31 s (1.2 %) |
| 10.49 Mbps, 0.06 % | h1→h6 while the link was down | same | `summary.md` window | mean over the 20 s outage |

## Experiment timeline

| Value | Meaning | Run | Source | How computed |
|---|---|---|---|---|
| 40 s + 3 × (25 s + 45 s) | baseline, then flood + recovery per case | R1–R3 | `meta.json` args | baseline 40, attack 25, recover 45 |
| 255 s | length of one run's timeline | R1 | `timeline.json` | `end` mark − `baseline_start` = 255.2 s (about 4.5 min including start-up and clean-up) |
| 10 Mbps UDP, ping every 0.5 s | legitimate traffic h1→h6 | all | `meta.json`, `ping_h1_h6.txt` | `iperf_rate` 10M |
| hping3 `--icmp --flood -d 1000` | attack command | all | `hping3_*.txt` | 1,000-byte payload |
| user / no delay | datapath and delay emulation of R1–R3 | R1–R3 | `meta.json` | `datapath: user`, `delay_emulated: false` |
| 0 % / 0 % | pingAll loss before traffic | R1 | `meta.json` | `pingall_loss_pct` |
