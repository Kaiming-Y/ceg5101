# CEG5101 CA2 Report — Anomaly-aware Routing and Blocking Controller

Name / Matric no.:            Date:

> Fill in the `TODO`s. Grading: conceptual understanding · logical design & reasoning ·
> analysis & interpretation of results. Figures come from `results/<run>/figures/`,
> numbers from `results/<run>/summary.md`.

## 1. Introduction
- TODO: Goal in 3–4 sentences: detect high-rate (DDoS-like) sources, block them, and reroute legitimate traffic using traffic- and anomaly-aware link costs.
- Environment: TODO (Mininet version, OVS version/datapath, Ryu 4.34, OpenFlow 1.3, VM spec).

## 2. Topology (Task 1)
- Screenshot ①: MiniEdit canvas. Screenshot ②: `pingall` 0% dropped.
- Table of the 11 switch links with C0 (= delay ms) and bw 40 Mbps.
- Static shortest path h1→h6 = s1-s2-s6 (19); second best s1-s2-s3-s6 (22).

## 3. Controller design
### 3.1 Architecture
- TODO: Diagram/description (see PLAN.md §1): topology discovery, ARP proxy, path-wide flow installation, monitoring loop.
### 3.2 Traffic monitoring & anomaly detection (Task 2)
- Per-source pps at the ingress switch from FlowStats every 2 s; ICMP echo replies excluded (why: D4).
- EMA baseline (α = 0.3) + adaptive threshold max(3·EMA, EMA + 4σ, 500 pps); check-before-update (D5, D6).
- Blocking: priority-5000 drop rule for `ipv4_src` on all switches. Evidence: screenshots ④⑤⑥, fig5.
### 3.3 Dynamic link cost (Task 3)
- Eq. (1) with α = 10, β = 30, Rmax = 40 Mbps; R_ij from PortStats (max of both directions, EMA-smoothed).
- How A_ij is set (links on the attacker's path) and kept while the attack hits the drop rule, plus a 10 s hold (D7, D8).
- Why β = 30: the backup path is 3 more expensive, so β must exceed 3 + margin.
### 3.4 Rerouting (Task 4)
- Per-flow "stay vs move" comparison including the flow's own load, margin = 2 (D9); install new path egress→ingress, then delete stale rules (D10).
- Recovery: A_ij → 0, cost → C0, flow moves back once the original path is cheaper by more than the margin.

## 4. Experiments
- Timeline: 40 s baseline → for each case: 25 s flood (`hping3 --icmp --flood -d 1000`), 45 s recovery.
- Legitimate flow: `iperf -u -b 10M` h1→h6 (+ 2 pps ping for RTT); 1 pps background pings from every host.

## 5. Results (Task 4 + 5)
Insert `summary.md` table here.

### 5.1 Case a — h2→h3 (s2–s3)
- Observation: TODO (cost of s2-s3 rises to …, h2 blocked after … s, h1→h6 path unchanged, no loss).
- Reason: TODO (no shared link with s1-s2-s6).
### 5.2 Case b — h2→h6 (s2–s6)
- Observation: TODO (loss peak …% for … s before detection, reroute to s1-s2-s3-s6 at block time, recovery at …).
- Reason: TODO (shared bottleneck s2-s6: 40 Mbps flood + 10 Mbps legit on a 40 Mbps link; β term dominates after the block).
### 5.3 Case c — h5→h6 (s5–s6)
- Observation: TODO. **Note**: Dijkstra routes h5→h6 via s5-s3-s6 (16 < 20), so s3-s5 / s3-s6 are flagged, not s5-s6.
- Optional controlled experiment (PLAN Phase 6.3).
### 5.4 Figures
- fig1 normalised cost vs time · fig2 packet loss vs time · fig3 throughput vs time · fig4 overview · fig5 blocking check.
- TODO: for each figure, 2–3 sentences linking the curve shape to the mechanism (load term vs β term, hold, hysteresis).

## 6. Discussion
- Detection delay (poll interval, partial first sample); trade-off with false positives (`CEG_CONSEC`).
- Path cost vs latency: backup path costs 3 more (≈ +6 ms RTT with real delays).
- Limitations: source-IP blocking vs spoofed sources; fixed hold time; empirical 500 pps floor; global block also stops the source's legitimate traffic.
- Optional: β / α sensitivity results (PLAN Phase 6).

## 7. Conclusion
- TODO

## Appendix
- Code listing: `controller/integrated_controller.py`, `controller/sdn_logic.py`.
- How to reproduce: README quick start.
