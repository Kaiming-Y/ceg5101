# CEG5101 CA2 执行计划（PLAN）

> 作业：**Anomaly-aware Routing and Blocking Controller**（满分 30）
> 本文件是后续执行的唯一依据：按 Phase 顺序做，每完成一项就把 `[ ]` 改成 `[x]`。
> 代码已写好：在云端容器里跑过 3 次 a,b,c（R1–R3，见 9.1 节和第 10 节），又在官方 Mininet 2.3.0 VM 里带链路时延跑过一次（见 9.2 节）。剩下的：自己手动在 MiniEdit 里画一遍（Task 1）、把 VM 的结果和新的 Task 1 图写进报告；有条件的话在有硬件虚拟化的 VM 上再跑一次（原因见 9.2 节末）。

---

## 0. 评分点 → 交付物 对照

| 评分项 | 分值 | 交付物 | 产生方式 | 状态 |
|---|---|---|---|---|
| 1. MiniEdit 拓扑 | 5 | MiniEdit 截图、`.mn` 文件、运行截图 | Phase 1 | ✅ 已在官方 Mininet 2.3.0 VM 的 MiniEdit 里通过 GUI 搭好并运行：`miniedit/my_topology.mn`、`miniedit/my_topology_export.py`、`report/figures/task1_miniedit_*.png`、`results/miniedit-vm/` · ⬜ 建议你们自己在 VM 里照步骤再搭一遍（Phase 1） |
| 2. 监控 + EMA 检测 + 封禁 | 5 | 控制器代码、block 事件日志、`dump-flows` 截图、fig5 | Phase 2 / 3 | ✅ 已完成（3 次重复 + CLI 演示截图） |
| 3. 动态链路代价 | 10 | Eq.(1) 实现、links.csv、fig1 | Phase 3 | ✅ 已完成 |
| 4. 合法流量改路由（a/b/c） | 10 | paths.csv、reroute 事件、summary.md 表格 | Phase 3 | ✅ 已完成（R1–R3 容器；Mininet VM 带链路时延复现一次，见 9.2） |
| 5. 性能评估 | — | fig1–fig5 + 文字分析 | Phase 4 / 5 | ✅ 报告已完成：`report/report.pdf`（LaTeX，见第 10 节） |

---

## 1. 总体设计（报告第 2 节可直接用）

```
            ┌──────────────── integrated_controller.py (Ryu, OF1.3) ────────────────┐
 LLDP ───►  │ 拓扑发现 (--observe-links) → adj{dpid:{nbr:port}}，判定 host 端口       │
 PacketIn ► │ ARP：代理应答 / 只向 host 端口投递（mesh 里不会广播风暴）                  │
            │ IPv4：Dijkstra(动态代价) → 整条路径一次下发 (egress→ingress)            │
            │       匹配 (ipv4_src, ipv4_dst, ip_proto[, icmpv4_type])                │
 每 2 s ──► │ FlowStats → 各源在 ingress 交换机的 pps（不计 ICMP echo reply）          │
            │ PortStats → 每条链路 R_ij(t) = max(两方向 tx 速率)，EMA 平滑             │
            │ AnomalyDetector：EMA 基线 + 自适应阈值 → 触发 block                       │
            │ block：所有交换机装 priority 5000 drop 规则；攻击流经过的链路 A_ij=1       │
            │ C_ij = C0 + α·R/Rmax + β·A → 对每个活跃流比较“留下 vs 换路”，带迟滞     │
            │ 攻击停止（drop 速率降下来）→ 等 hold 后 A_ij=0 → 代价恢复 → 路由回切     │
            └──────────────────────────────────────────────────────────────────────┘
```

### 关键设计决策和理由（报告“Logical Design and Reasoning”部分的素材）

| # | 问题（参考代码的缺陷） | 本项目的做法 |
|---|---|---|
| D1 | `resilient_controller.py` 的 `predefined_costs` 是旧的 4 交换机拓扑 | `sdn_logic.BASE_COSTS` 按 `ceg_mesh_topo.py` 的 11 条链路重写（C0 = delay ms） |
| D2 | 原转发流表只匹配 `eth_dst`，FlowStats 里没有 `ipv4_src`，检测拿不到数据 | 流表匹配 `ipv4_src/ipv4_dst/ip_proto(/icmpv4_type)` |
| D3 | 同一个包在路径上每台交换机都被统计一次 | 只在源主机所连的 ingress 交换机计数 |
| D4 | ICMP 洪泛时受害者会回同样多的 echo reply，会被误判为攻击者（case b 会把 h6 封掉，h1→h6 就断了） | 统计源速率时排除 `icmpv4_type=0` |
| D5 | 参考代码先更新 EMA 再比较，实际阈值约等于 21×baseline；而且会把攻击样本学进基线 | 先比较、后更新；异常样本不学习 |
| D6 | 固定 3× 阈值（作业指出的 limitation a） | 阈值 = max(3·EMA, EMA + 4·σ, 500 pps)，σ 为指数加权标准差；另有 warm-up 期 |
| D7 | 封禁后攻击流在 ingress 就被丢弃，R_ij 很快降到 0，只靠负载项无法维持改路由 | 用 drop 规则的计数判断“攻击是否还在”；还在就保持 A_ij=1，停止后再保持 `hold` 秒 |
| D8 | 源的正常流量（比如 1 pps ping）也会命中 drop 规则，导致永远解封不了 | “攻击仍在”的判据是 drop 速率 ≥ 0.5×检测阈值 |
| D9 | 负载项会把流自己的流量算进当前路径代价，造成来回振荡 | 比较时把本流速率加到候选路径上（what-if），并要求新路径便宜 `margin=2` 以上 |
| D10 | 原代码只在 packet-in 时逐跳算路，已装好的流表不会改 | 主动整条路径重装（先下游后上游），再删除旧路径上多余的规则 |
| D11 | mesh 拓扑里 MST/泛洪在 LLDP 完成前会形成广播风暴 | 拓扑就绪前丢弃 packet-in；ARP 走代理应答，未知目标时只投递到 host 端口 |
| D13 | 链路断开后已发现链路数 < 11，控制器会退回“未就绪”，停止监控并忽略 ARP，主机在断链期间失联 | 首次完整发现后锁存就绪状态（在链路故障实验中发现并修复） |
| D12 | case a 和 b 的攻击者都是 h2，封禁后不解封的话 case b 无法复现 | 安静 `unblock_quiet` 秒后自动解封（`CEG_AUTO_UNBLOCK=0` 可关闭） |
| D14 | 有链路时延时 pingAll 变慢，h1 的 iperf 在 5 个样本的 warm-up 结束后才开始：第一个只覆盖部分周期的样本（377 pps）被学进基线，下一个样本 920 pps 超过阈值 804，h1 自己被封（在 Mininet VM 上发现，`results/vm-delay-abc-warmup5/`） | 模拟链路时延、控制器由 `run_experiment.py` 启动且没设 `CEG_WARMUP` 时，runner 自动设 `CEG_WARMUP=12`（约 24 s，比观测到的 topology_ready→iperf 14 s 多约 10 s 余量）；外部控制器要自己设。代价：`--baseline` 很短（约 10 s 以下）时，攻击可能落在攻击者的 warm-up 里被学进基线；文档里的命令都用 30–40 s |

### 参数（`controller/sdn_logic.py: Config`，都可以用环境变量覆盖）

| 参数 | 默认 | 环境变量 | 说明 |
|---|---|---|---|
| poll interval | 2 s | `CEG_POLL` | 统计请求周期 |
| Rmax | 40 Mbps | `CEG_RMAX_MBPS` | = TCLink bw |
| α | 10 | `CEG_ALPHA` | 链路满载时代价 +10 |
| β | 30 | `CEG_BETA` | 必须 > 3 + margin 才能让 case b 改路由（备用路径贵 3） |
| margin | 2 | `CEG_MARGIN` | 改路由的迟滞量 |
| EMA α | 0.3 | `CEG_EMA_ALPHA` | 和参考代码一致 |
| k / kσ / floor | 3 / 4 / 500 pps | `CEG_K` / `CEG_K_SIGMA` / `CEG_MIN_PPS` | 自适应阈值 |
| warm-up | 5 个样本（模拟链路时延时 runner 自动用 12，见 D14） | `CEG_WARMUP` | 从该源第一次出现（pingAll 时）开始计 |
| consecutive | 1 | `CEG_CONSEC` | 连续超阈值次数 |
| hold | 10 s | `CEG_HOLD` | 攻击停止后 A_ij 再保持多久 |
| unblock quiet | 10 s | `CEG_UNBLOCK_QUIET` | 安静多久后解封 |

### 预期结果（`python3 analysis/expected_paths.py`）

| case | 洪泛 | 题目说的链路 | 攻击实际路径 | h1→h6 攻击期间 | 改路由？ |
|---|---|---|---|---|---|
| 基线 | — | — | — | s1-s2-s6 (19) | — |
| a | h2→h3 | s2–s3 | s2-s3 | s1-s2-s6 | 否（不重叠） |
| b | h2→h6 | s2–s6 | s2-s6 | **s1-s2-s3-s6 (22)** | **是** |
| c | h5→h6 | s5–s6 | **s5-s3-s6**（16 < 20） | s1-s2-s6 | 否 |

⚠️ case c 是报告里必须指出的点：按给定代价 h5→h6 根本不走 s5–s6。可选的补充实验见 Phase 6.3。

---

## Phase 0 — 环境准备

目标环境：Mininet VM（Ubuntu 20.04）或任意 Ubuntu 20.04/22.04/24.04 虚拟机。

> ✅ 已验证（2026-11-03）：官方 Mininet 2.3.0 VM 镜像 `mininet-2.3.0-210211-ubuntu-20.04.1-legacy-server-amd64`（Ubuntu 20.04.1、kernel 5.4、OVS 2.13.8 内核 datapath、sch_netem、Python 3.8.10）。`scripts/setup_ubuntu.sh` 原样运行（VM 里的副本与仓库里的逐字节相同；只额外配置了我们云端网络需要的 apt 代理，你的 VM 不需要），装好 `ryu-manager 4.34`，18 个单元测试全部通过。这个 VM 是在云端容器里用 `scripts/qemu_mininet_vm.sh` 以 QEMU 纯软件模拟（TCG，无 KVM，4 vCPU / 4 GB）启动的，所以很慢，见 9.2 节。

- [ ] 0.1 把整个 `ceg5101-sdn-lab/` 拷到虚拟机上（用 `scripts/qemu_mininet_vm.sh` 启动的 VM：`scp -P 2222 -r ceg5101-sdn-lab mininet@127.0.0.1:`，密码 `mininet`）
- [ ] 0.2 `bash scripts/setup_ubuntu.sh`：装 OVS / hping3 / iperf / tcpdump / ethtool / python3-tk，并创建 Ryu 4.34 的虚拟环境 `~/ryu-venv`
- [ ] 0.3 设置环境变量（建议写进 `~/.bashrc`）
  ```bash
  export RYU_MANAGER=$HOME/ryu-venv/bin/ryu-manager
  export PLOT_PYTHON=$HOME/ryu-venv/bin/python
  ```
- [ ] 0.4 单元测试：`python3 -m unittest discover -s tests -v`，应为 18/18 OK
- [ ] 0.5 `python3 analysis/expected_paths.py`，输出应与上表一致

验收：`$RYU_MANAGER --version` 输出 `ryu-manager 4.34`；`sudo mn --test pingall` 能通过。

---

## Phase 1 — MiniEdit 拓扑（Task 1，5 分，需要图形界面）

题目要求“在 MiniEdit 里创建并运行”，所以至少要手动画一遍并截图。`.mn` 文件是备用和对照。

> ✅ 已做过一遍（2026-11-03，官方 Mininet 2.3.0 VM 里 Mininet 自带的 MiniEdit，About 里的版本号是 2.2.0.1）：MiniEdit 通过 `ssh -Y` 显示。所用的 miniedit.py 打了下面排错里的 `wb`→`w` 补丁。
>
> 步骤与下面 1.3–1.8 相同：用工具栏放 s1–s6、h1–h6、c0；拖 17 条数据链路和 6 条控制链路；在 Link Details 里逐条填 bw 40 和 delay；在 Host Properties 里填 10.0.0.i/24；c0 改为 Remote Controller（127.0.0.1:6633 是默认值）；Edit → Preferences 只勾 OpenFlow 1.3 和 Start CLI；File → Save → `miniedit/my_topology.mn`；File → Export Level 2 Script → `miniedit/my_topology_export.py`。
>
> 检查：`.mn` 的 17 条链路（bw/delay）和主机 IP 与 `topology/ceg_mesh_topo.py` 完全一致（`.mn` 不存 DPID，Mininet 按交换机名给的默认值与拓扑文件相同）。点 Run 后约 23 s 控制器报 `topology_ready`；MiniEdit 的 CLI 里 `pingall` 0% dropped（30/30），`h1 ping -c 4 h6` 的 rtt min/avg/max = 99.8/101.3/105.3 ms（理论 2×(15+5+14+15) = 98 ms，路径 s1-s2-s6）；控制台对每条链路显示 `(40.00Mbit Xms delay)`。
>
> 产物：`report/figures/task1_miniedit_canvas.png`（画布截图）、`report/figures/task1_miniedit_running.png`（拼图：运行中的画布 + MiniEdit CLI + Ryu 事件）、`results/miniedit-vm/`（截图、7 分钟原始录屏）、`presentation/video/miniedit_build.mp4`（35 s，12 倍速）。原来的容器截图改名保留为 `results/miniedit-demo/*_container_loaded.png`。

**建议你们自己在 VM 里照上面的步骤再搭一遍**（约 20 分钟），用自己的截图。画完把你保存的 `.mn` 和 `miniedit/my_topology.mn` 对照（只比链路的 bw/delay 和主机 IP，不比坐标；没有输出差异就说明一致）：
```bash
mnkey() { python3 -c "import json,sys;d=json.load(open(sys.argv[1]));[print(*sorted([l['src'],l['dest']]),l['opts'].get('bw'),l['opts'].get('delay')) for l in d['links']];[print(h['opts']['hostname'],h['opts'].get('ip')) for h in d['hosts']]" "$1" | sort; }
diff <(mnkey miniedit/my_topology.mn) <(mnkey miniedit/my_topology_manual.mn) && echo 一致
```

- [ ] 1.1 启动控制器（另开一个终端）：
  ```bash
  cd ceg5101-sdn-lab
  CEG_LOG_DIR=results/miniedit/controller $RYU_MANAGER --observe-links controller/integrated_controller.py
  ```
- [ ] 1.2 `sudo python3 $(python3 -c "import mininet,os;print(os.path.dirname(mininet.__file__))")/examples/miniedit.py`
  （Mininet VM 上通常是 `sudo ~/mininet/examples/miniedit.py`。官方 VM 没有图形界面：从有 X 的机器 `ssh -Y` 登录，再用 `sudo -E XAUTHORITY=$HOME/.Xauthority python3 ~/mininet/examples/miniedit.py` 启动；上面的 GUI 构建就是这样启动的）
- [ ] 1.3 Edit → Preferences：勾选 **OpenFlow 1.3**；Start CLI 可以勾上
- [ ] 1.4 手动画：s1–s6、h1–h6（IP 填 10.0.0.x/24；Switch 的 DPID 可以填 000000000000000x，留空也行，默认值相同，GUI 构建时就是留空的）
  - host 链路：`s_i–h_i`，bw 40，delay 15ms（Link Details 里 Bandwidth 填 `40`，Delay 带单位填 `15ms`）
  - 交换机链路（bw 都是 40）：s1-s2 5ms，s2-s3 10ms，s4-s5 15ms，s5-s6 20ms，s1-s4 8ms，s2-s5 12ms，s3-s6 7ms，s1-s5 18ms，s2-s4 6ms，s2-s6 14ms，s3-s5 9ms
  - 控制器 c0：Remote Controller，127.0.0.1:6633（IP 和端口是默认值，只需要改类型）
  - 备选：File → Open `miniedit/ceg_mesh_topo.mn`（由 `miniedit/make_mn.py` 生成，布局与 `miniedit/preview_loaded.png` 一致）
- [ ] 1.5 **截图 ①**：完整画布
- [ ] 1.6 点 Run，等控制器终端出现 `topology_ready`（在上面的 VM 里约 23 s），再在 MiniEdit 的 CLI 里执行 `pingall`（第一次可能有少量丢包，等 LLDP 完成后再跑一次）
- [ ] 1.7 **截图 ②**：pingall 0% dropped；**截图 ③**：控制器终端的 `topology_ready` / `Host learned` 日志
- [ ] 1.8 File → Save 成你自己的文件，例如 `miniedit/my_topology_manual.mn`（不要覆盖仓库里用来对照的 `my_topology.mn`）；可选 File → Export Level 2 Script。**Mininet 2.3.0 自带的 MiniEdit 在 Python 3 下保存会失败**，先按下面排错第一条打补丁

排错：
- File → Save / Export 之后文件是 0 字节，终端显示 `a bytes-like object is required, not 'str'`（Export 会打印 Tk 回调的 traceback）：Mininet 2.3.0 自带 miniedit.py 的上游 bug，`saveTopology` 和 `exportScript` 用 `open(fileName, 'wb')` 打开文件再写 str（官方 VM 上是第 1686、1705 行）。修复：把这两处改成 `'w'`：
  ```bash
  sudo sed -i.orig "s/open(fileName, 'wb')/open(fileName, 'w')/" ~/mininet/examples/miniedit.py
  ```
  如果你用 1.2 的第一条命令启动的是安装目录里的副本（官方 VM 上是 `/usr/local/lib/python3.8/dist-packages/mininet/examples/miniedit.py`），那一份也要改。
- 加载 `.mn` 时报 `dict_items + dict_items` 的错：说明这个 MiniEdit 版本加载 preferences 有 bug。我们生成的 `.mn` 已经不含 preferences；如果用的是你自己保存的文件，删掉其中的 `"application"` 段即可。仓库里的 `my_topology.mn` 是 MiniEdit 自己保存的，含 `"application"` 段，在 2.3.0 的 MiniEdit 里 File → Open 也会遇到这个错（第 1452 行）；它只用来对照，要直接加载请用 `ceg_mesh_topo.mn`。
- Export Level 2 Script 导出的脚本不保留“只用 OpenFlow 1.3”这个设置（导出代码不写 `protocols=`，也不写 dpid）。直接运行也能和 Ryu 协商到 1.3（OVS 2.13 默认就启用 1.3）；想严格限定就在每个 `addSwitch` 里手动加 `protocols='OpenFlow13'`。
- Host / Switch Properties 弹窗没有自己的标题（MiniEdit 的 `CustomDialog` 忽略了标题参数），就是右键 → Properties 后弹出的那个小窗口。
- pingall 不通：确认 OpenFlow 1.3 已勾选、控制器带了 `--observe-links`、控制器日志里出现了 `topology_ready`。

---

## Phase 2 — 手动演示 Task 2（检测 + 封禁），供截图

另一种做法：直接跑 Phase 3 的自动脚本，证据已经全部写进 `results/<run>/`。这里的手动步骤是为了拿到“看得见”的截图。

- [ ] 2.1 终端 A：`CEG_LOG_DIR=results/manual/controller $RYU_MANAGER --observe-links controller/integrated_controller.py`
- [ ] 2.2 终端 B：
  ```bash
  sudo mn --custom topology/ceg_mesh_topo.py --topo meshTopo --link tc \
          --controller remote,ip=127.0.0.1,port=6633 --switch ovsk,protocols=OpenFlow13 --mac
  ```
  （容器或没有 OVS 内核模块的环境，用 `--switch ovsk,protocols=OpenFlow13,datapath=user`）
- [ ] 2.3 在 Mininet CLI 里执行：
  ```
  mininet> pingall
  mininet> h2 ping -i 1 h3 > /tmp/h2ping.txt &        # 建立 h2 的正常基线（≥ 15 s）
  mininet> sh sleep 15
  mininet> h2 hping3 --icmp --flood -d 1000 h3 &      # 注意：题目写的 "-icmp" 是笔误
  mininet> sh sleep 6
  mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s2 | grep 5000     # 截图 ④：drop 规则 n_packets 在涨
  mininet> h3 timeout 3 tcpdump -n -i h3-eth0 icmp and src host 10.0.0.2   # 截图 ⑤：0 packets
  mininet> h2 pkill hping3
  ```
- [ ] 2.4 **截图 ⑥**：控制器日志里的 `[EVENT] block h2->h3 {... "pps": ..., "baseline": ..., "threshold": ...}`
- [ ] 2.5 `results/manual/controller/sources.csv` 里能看到 h2 的 pps / baseline / threshold 随时间的变化（报告可以画一张小图）

---

## Phase 3 — 自动实验（Task 3 + 4 + 5 的全部数据）

```bash
cd ceg5101-sdn-lab
sudo -E python3 experiments/run_experiment.py            # a,b,c 连续跑，约 5 分钟
```

时间线（默认值）：基线 40 s → [洪泛 25 s → 恢复 45 s] × 3。h1→h6 全程跑 UDP iperf 10 Mbps 和 2 pps ping；其余主机 1 pps 背景 ping。

**有链路时延时的 warm-up（D14，2026-11-03 在 Mininet VM 上发现）**：检测器对每个源先学 `CEG_WARMUP` 个样本（默认 5 个，约 10 s，从该源第一次出现、也就是 pingAll 时开始计）再判定。容器里没有时延，pingAll 很快，h1 的 iperf 在 warm-up 期内就开始了，被学进基线。有时延时，runner 的两次 pingAll 加 1 s sleep 约 13 s，topology_ready 到 iperf 开始约 14 s，h1 的第 5 个 warm-up 样本在 iperf 开始前 2.9 s 就取完了。iperf 的第一个样本只覆盖部分周期（377 pps，低于 500 pps 下限，所以被学进基线：基线 113.4 pps，阈值 803.9），下一个样本 919.9 pps 超过阈值，**h1 自己被封**（iperf 开始后 4.4 s），h1→h6 整场吞吐为 0（`results/vm-delay-abc-warmup5/`，整场无效）。
- 处理：模拟链路时延、控制器由脚本自己启动（默认 `--controller auto`）且没设 `CEG_WARMUP` 时，`run_experiment.py` 自动设 `CEG_WARMUP=12`，并把传给控制器的 `CEG_*` 环境变量写进 `meta.json` 的 `ceg_env_passed_to_controller`（`CEG_WARMUP` 设成空字符串也按“没设”处理）。
- `results/vm-delay-abc/` 是手动设 `CEG_WARMUP=12` 跑的；自动默认值是在它之后加的，所以它的 `meta.json` 里没有 `ceg_env_passed_to_controller`，以 `controller/config.json` 里的 `warmup_samples: 12` 为准。自动设置这条路径目前只用桩程序做过 dry run，还没有在真实 Mininet 里跑过。
- 自动默认值已在 VM 上实跑验证（`results/vm-autowarmup-b/`，只跑 case b，没设 `CEG_WARMUP`）：日志打印 `using CEG_WARMUP=12`，`config.json` 里 `warmup_samples: 12`，`meta.json` 里 `ceg_env_passed_to_controller = {'CEG_WARMUP': '12'}`；h1 没被误封，h2 3.2 s 被封，h1→h6 改走 s1-s2-s3-s6 后回切。
- 要换别的值：`sudo -E env CEG_WARMUP=N python3 experiments/run_experiment.py ...`（普通 `sudo` 会丢掉 `CEG_*`）。
- `--controller external` 时 runner 改不了已经在运行的控制器，见 3.5。

- [ ] 3.1 跑完整的 a,b,c → `results/<时间戳>/`
- [ ] 3.2 检查 `summary.md`，验收标准：
  - [ ] 三个 case 都是 `blocked = yes`，detect delay < 6 s
  - [ ] “attack pkts at victim … pps after” 在封禁后为 0
  - [ ] case b：h1→h6 攻击期间走 `s1-s2-s3-s6`，after 回到 `s1-s2-s6`
  - [ ] case a、c：h1→h6 始终是 `s1-s2-s6`
  - [ ] 三段 after 的吞吐 ≈ 10.5 Mbps、丢包 ≈ 0
  - [ ] `controller/events.csv` 里没有 h1（10.0.0.1）的 block；如果有，而且 h1→h6 吞吐从头到尾是 0，就是上面说的 warm-up 误封
- [ ] 3.3 建议再跑 2 次，取稳定的一次（或者报告里给出均值）
- [ ] 3.4 单独跑某一个 case：`--scenarios b --attack 20 --recover 40`
- [ ] 3.5 已经开着控制器时：`--controller external`（并让控制器的 `CEG_LOG_DIR` 指向 `<out>/controller`）。有链路时延时控制器要自己带上 `CEG_WARMUP=12` 启动：
  `CEG_WARMUP=12 CEG_LOG_DIR=<out>/controller $RYU_MANAGER --observe-links controller/integrated_controller.py`。这种模式下 runner 不记录 `ceg_env_passed_to_controller`（它传不到控制器），控制器实际用的参数以 `<out>/controller/config.json` 为准

产物说明：

| 文件 | 内容 |
|---|---|
| `controller/links.csv` | 每 2 s 每条链路的 rate、util、A、cost、C/C0 |
| `controller/paths.csv` | 每 2 s 每个活跃流的路径和当前代价 |
| `controller/sources.csv` | 每个源的 pps、EMA 基线、阈值、是否被封 |
| `controller/events.csv` | topology_ready / path_set / block / unblock / reroute |
| `controller/config.json` | 控制器实际使用的参数（例如 `warmup_samples`） |
| `meta.json` | datapath、是否模拟了链路时延、命令行参数、pingall 丢包、`ceg_env_passed_to_controller`（仅 auto 模式） |
| `iperf_server.txt` | h6 侧每秒的吞吐与丢包（`-e` 格式） |
| `ping_h1_h6.txt` | h1→h6 RTT（带时间戳） |
| `victim_capture_<x>.txt` | 受害者收到的、来自攻击者的 ICMP（tcpdump） |
| `attack_counters.csv` | 攻击者 tx 计数（算发送速率） |
| `flows/*.txt` | 基线 / 攻击中 / 恢复后 所有交换机的 dump-flows |
| `figures/fig1–5.png`, `summary.md` | 由 `analysis/plot_results.py` 自动生成 |

---

## Phase 4 — 图表（Task 5.3）

自动脚本跑完会自动调用 `analysis/plot_results.py`。如果失败，手动执行：
`$PLOT_PYTHON analysis/plot_results.py results/<run>`

| 图 | 对应题目 |
|---|---|
| `fig1_link_cost.png` | 5.3a Dynamic Link Cost (normalized) vs Time（6 条关键链路的小多图） |
| `fig2_packet_loss.png` | 5.3b Packet Loss (%) vs Time |
| `fig3_throughput.png` | 5.3c Throughput (Mbps) vs Time |
| `fig4_overview.png` | 路径 + 代价 + 丢包 + 吞吐 + RTT 在同一时间轴（报告的主图） |
| `fig5_blocking.png` | Task 2 的封禁证据：发送 vs 到达受害者 |

- [ ] 4.1 打开每张图检查：阴影区为洪泛期、虚线为封禁、点线为 h1→h6 改路由
- [ ] 4.2 需要更大的字号或不同配色时，改 `plot_results.py` 顶部的常量

---

## Phase 5 — 报告（`report/REPORT_TEMPLATE.md`）

- [ ] 5.1 按模板结构写（评分三项：Conceptual / Design & Reasoning / Analysis）
- [ ] 5.2 放截图 ①–⑥、fig1–fig5、summary 表格
- [ ] 5.3 分析要点（每个 case 写“观察 → 原因”）：
  - 代价：被攻击链路 C/C0 从约 1.0（基线负载很低）在洪泛开始时冲到峰值（负载项 + β 项），封禁后负载项消失，只剩 β 项（平台），攻击停止约 hold+poll 秒后回到 1
  - 路径：只有 case b 的攻击链路和 h1 的路径重合，所以只有 b 改路由；改路由和封禁发生在同一个评估周期
  - 丢包/吞吐：case b 在检测前约 2–4 s 内 s2-s6 被打满（40 Mbps 洪泛 + 10 Mbps 合法流），h1 丢包峰值约 45%、吞吐跌到约 5.5 Mbps；封禁后立即恢复。a、c 几乎无影响（以上是容器的数字。VM 上 b 的最差 1 s 丢包只有 11.2%，但排队时延很大，RTT 到 383 ms；c 反而有 10.4%，原因见 9.2）
  - 代价权衡：备用路径 C0=22 比 19 贵，正常情况下不会选；RTT 在 b 期间理论上多 6 ms（往返多 2×3 ms）。VM 实测（`vm-delay-abc`）h1→h6 RTT 中位数：基线 99.8 ms → 绕路 109.0 ms（最小 106 ms；洪泛还在时 111 ms，洪泛结束后 107 ms）→ 回切后 100.0 ms
  - case c：说明 Dijkstra 走 s5-s3-s6，被标记异常的是 s3-s5 和 s3-s6；要真正压 s5–s6，见 Phase 6.3
  - 检测延迟 = 轮询周期 + 起始样本只覆盖部分周期；以及“攻击开始时的部分样本被学进基线”的现象（case b 的基线是 148 pps，不是 1 pps）
  - 局限：源 IP 封禁会误伤伪造源 IP 的场景；固定 hold；阈值下限是经验值
- [ ] 5.4 附代码：`controller/` 两个文件 + `topology/` + `experiments/`

---

## Phase 6 — 可选加分 / 扩展实验

- [x] 6.1 β 敏感性：`CEG_BETA=2`（低于 3+margin，应当不改路由）vs 30 vs 100，比较 case b
  ```bash
  sudo -E env CEG_BETA=2 python3 experiments/run_experiment.py --scenarios b --out results/beta2
  ```
- [x] 6.2 α 敏感性 / 关闭 β（`CEG_BETA=0`）：只靠负载项时，封禁后立刻回切（展示 D7 的必要性）
- [x] 6.3 真正压 s5–s6：`sudo -E env CEG_COST_OVERRIDE=5-6:8 python3 experiments/run_experiment.py --scenarios c --baseline 30`（不用改代码）→ `results/exp-c-s5s6-cost8/`
- [x] 6.4 链路故障韧性：`sudo -E python3 experiments/run_experiment.py --scenarios "" --baseline 30 --fail-link s2-s6 --fail-for 20 --recover 30` → `results/exp-linkfail-s2s6/`（这个实验发现并修复了一个 bug：链路断开时控制器曾退回“拓扑未就绪”状态，导致 ARP 被忽略）
- [ ] 6.5 `CEG_CONSEC=2`：误报更少，代价是检测延迟增加一个周期

---

## 7. 已知问题与排错

| 现象 | 原因 / 处理 |
|---|---|
| `ryu-manager` 装不上 / 运行时报 eventlet 错误 | 只能用 Python ≤ 3.9 + `eventlet==0.30.2` + `setuptools<58`；用 `scripts/setup_ubuntu.sh` |
| `Specified qdisc kind is unknown`（netem） | 内核没有 sch_netem（容器常见）。脚本会自动去掉 delay；路由代价在控制器里，结论不受影响，只是 RTT 偏小 |
| TCP iperf 卡住 | 用户态 OVS 下 TCP 会卡住，实验只用 UDP（反正需要测丢包） |
| pingall 首次有丢包 | LLDP 未完成或 ARP 还没学到；脚本会先跑两次 pingall |
| 某个 case 没检测到 | 攻击源没有基线（没跑背景 ping）或处在 warm-up；看 `sources.csv` |
| 拆网时出现一串 link_down | 正常，summary 已过滤掉 `end` 之后的事件 |
| `mn -c` 之后 OVS 起不来 | `sudo service openvswitch-switch restart` |
| MiniEdit File → Save / Export 得到 0 字节文件（`a bytes-like object is required`） | Mininet 2.3.0 自带 miniedit.py 的上游 bug（`open(fileName, 'wb')` 写 str）。把两处 `'wb'` 改成 `'w'`，命令见 Phase 1 排错 |
| 写 `summary.md` 时报 `UnicodeEncodeError`（Mininet VM 的 locale 是 `LANG=en_US`，默认编码 ISO-8859-1，写不了 `→`） | 已修复：`analysis/plot_results.py`、`experiments/run_experiment.py`、`controller/integrated_controller.py`、`miniedit/make_mn.py` 里所有文本 `open()` 都加了 `encoding='utf-8'`，UTF-8 环境下输出逐字节不变。拷到 VM 上的必须是修复后的版本 |
| 有链路时延时 h1 一开始就被封，h1→h6 吞吐整场为 0（`events.csv` 里有 block 10.0.0.1） | warm-up 在 h1 的 iperf 开始前就结束了（Phase 3、D14）。runner 自己启动控制器时会自动用 `CEG_WARMUP=12`；外部控制器要手动设；也不要把 `CEG_WARMUP` 设成空字符串（runner 会当作“已设置”而不补默认值，控制器又会当作没设而用 5） |
| QEMU 纯软件模拟（无 KVM）的 VM 里洪泛打不满 40 Mbit/s、RTT 偶尔有几百 ms 的尖峰 | 模拟出来的 CPU 太慢，见 9.2；结论不受影响，但丢包和 RTT 的数字不能直接和容器比 |

---

## 8. 文件地图

```
ceg5101-sdn-lab/
├── PLAN.md                        ← 本文件
├── README.md                      快速开始
├── original/                      题目 PDF + 原始参考代码（不改）
├── topology/ceg_mesh_topo.py      题目给的拓扑（未改）
├── controller/
│   ├── integrated_controller.py   Ryu 应用：检测 + 封禁 + 动态代价 + 改路由
│   └── sdn_logic.py               纯逻辑：Config / BASE_COSTS / Eq.(1) / Dijkstra / 检测器
├── experiments/run_experiment.py  自动实验（Mininet）
├── analysis/
│   ├── plot_results.py            fig1–5 + summary.md
│   └── expected_paths.py          理论预期路径
├── tests/test_sdn_logic.py        18 个单元测试
├── miniedit/
│   ├── make_mn.py、ceg_mesh_topo.mn、preview_loaded.png   生成的 .mn（可以直接 File → Open）
│   ├── my_topology.mn、my_topology_export.py             VM 里用 MiniEdit GUI 保存 / 导出的（对照用）
├── report/                        REPORT_TEMPLATE.md（骨架）、report.tex / report.pdf、figures/
├── scripts/
│   ├── setup_ubuntu.sh            一键安装（已在官方 Mininet 2.3.0 VM 上验证）
│   └── qemu_mininet_vm.sh         在没有 KVM 的容器里用 QEMU 启动官方 Mininet VM
├── presentation/video/            miniedit_build.mp4（MiniEdit 搭建过程，12 倍速）
└── results/                       validation-abc（R1，参考用）、vm-delay-abc（VM）等，见第 10 节
```

---

## 9. 已完成的验证运行

### 9.1 云端容器（2026-10-22，R1）

环境：Ubuntu 24.04、Mininet 2.3.0、OVS 3.3.9 **用户态 datapath**、Ryu 4.34 / Python 3.9；**没有 netem，所以没有链路时延**。
命令：`run_experiment.py`（默认参数，a,b,c）。产物：`results/validation-abc/`。

| case | 检测延迟 | 异常链路 | h1→h6 前 / 中 / 后 | 吞吐 Mbps 前/中/后 | 丢包 % 前/中/后 | 封禁后到达受害者 |
|---|---|---|---|---|---|---|
| a h2→h3 | 3.4 s | s2-s3 | s1-s2-s6 / 不变 / s1-s2-s6 | 10.50 / 10.50 / 10.50 | 0 / 0 / 0 | 0 pps |
| b h2→h6 | 3.8 s | s2-s6 | s1-s2-s6 / **s1-s2-s3-s6** / s1-s2-s6 | 10.50 / 9.90 / 10.50 | 0 / 5.67（峰值约 47） / 0 | 0 pps |
| c h5→h6 | 1.7 s | s3-s5, s3-s6 | s1-s2-s6 / 不变 / s1-s2-s6 | 10.50 / 10.49 / 10.50 | 0 / 0.12 / 0 | 0 pps |

case b 的事件序列：t=115.6 s block h2，同一时刻 reroute h1→h6（代价 58.8 → 30.0）→ t≈140 s 洪泛结束 → t=151.6 s 解封，并回切 s1-s2-s6（30.1 → 24.5）。

### 9.2 官方 Mininet 2.3.0 VM，有链路时延（2026-11-03）

环境：官方镜像 `mininet-2.3.0-210211-ubuntu-20.04.1-legacy-server-amd64`，在云端容器里用 QEMU 8.2 纯软件模拟启动（TCG，无 KVM，4 vCPU / 4 GB，`scripts/qemu_mininet_vm.sh`）；Ubuntu 20.04.1、kernel 5.4、**OVS 2.13.8 内核 datapath**、**sch_netem（有链路时延）**、Python 3.8.10、Ryu 4.34。
命令：`run_experiment.py` 默认参数（a,b,c），手动设 `CEG_WARMUP=12`。产物：`results/vm-delay-abc/`。

| case | 检测延迟 | 封禁 | 异常链路 | h1→h6 前 / 中 / 后 | 吞吐 Mbps 前/中/后（最小 1 s） | 丢包 % 前/中/后（最差 1 s；R1 最差） | 封禁后到达受害者 |
|---|---|---|---|---|---|---|---|
| a h2→h3 | 2.2 s | h2 | s2-s3 | s1-s2-s6 / 不变 / s1-s2-s6 | 10.50 / 10.48 / 10.50（10.40） | 0 / 0 / 0（0；R1 0） | 0 pps |
| b h2→h6 | 1.6 s | h2 | s2-s6 | s1-s2-s6 / **s1-s2-s3-s6** / s1-s2-s6 | 10.49 / 10.47 / 10.49（9.84） | 0 / 0.45 / 0.02（11.2；R1 48.4） | 0 pps |
| c h5→h6 | 3.8 s | h5 | s3-s5, s3-s6 | s1-s2-s6 / 不变 / s1-s2-s6 | 10.49 / 10.42 / 10.50（8.95） | 0.02 / 0.66 / 0（10.4；R1 2.5） | 0 pps |

和容器（R1–R3）一致的地方：三个 case 都封禁了，封的主机和标异常的链路相同；只有 b 改路由；封禁 1 s 之后受害者收到的攻击包为 0；s2-s6 的 C/C0 平台值是 3.1429（= 44/14），与 R1 相同。检测延迟 2.17 / 1.59 / 3.85 s，与 R1–R3 的 1.47–3.76 s 相当（c 略高于上沿）。

case b 的事件序列：t=116.9 s 封禁 h2，同一时刻 h1→h6 改走 s1-s2-s3-s6（代价 54.96 → 30.2）→ t=156.1 s 解封 h2，h1→h6 回切 s1-s2-s6（30.08 → 24.32）。按容器的口径（攻击开始 + 25 s）算，回切在洪泛结束后 15.8 s，比 R1–R3 的 13.6–14.9 s 晚约 1–2 s。

容器做不到的：**RTT 能看出改路由**。h1→h6 RTT 中位数：基线 99.8 ms（理论 2×(15+5+14+15) = 98 ms）→ 绕路 109.0 ms（最小 106 ms，理论 104 ms；洪泛还在时 111 ms，洪泛结束后 107 ms）→ 回切后 100.0 ms。

和容器不同、写报告时要说明的地方：
- 洪泛弱一些：纯软件模拟下攻击者网卡在检测前只发出约 3,000–3,900 pkt/s（R1 约 4,800 pkt/s，即 40 Mbit/s 的上限），b、c 里到达受害者的约 20 Mbit/s，约为 R1 的七成。主要瓶颈在攻击者自己的发送路径（OVS 转发了攻击者网卡发出的大部分包）。hping3 自己报的 “transmitted” 数（约 37 万）大多没离开攻击者的队列，不能和容器的约 12 万比。
- 排队时延大、丢包形态不同：有时延的链路上有 netem 队列（Mininet 没设 `max_queue_size` 时用 netem 默认的 1000 个包，40 Mbit/s 下约 200 ms）。检测前 h1→h6 的 RTT 最高 383 ms（b）/ 408 ms（c），R1 约 20 ms。最差 1 s 丢包 b 11.2%（R1–R3 为 48.4 / 56.6 / 34.4%），c 10.4%（R1–R3 为 2.5 / 4.1 / 6.1%）；c 的检测较慢（第一个洪泛样本只覆盖了部分周期，37 pps），暴露时间更长。所以 VM 和容器的丢包数字不能直接比较。
- 封禁时已经在 netem 队列里的攻击包还会在之后 0.16–0.52 s 内陆续到达（a/b/c 分别 577 / 487 / 1188 个；R1 为 31 / 26 / 87），1 s 之后为 0。
- 实际洪泛约 25.2 s。timeline 里 attack_start → attack_end 两个标记之间是 27–28 s，多出来的是脚本的收尾步骤（R1 也有 26.7 s）。
- 纯软件模拟偶尔会停顿（例如 case a 里 +65.6 s 的 328 ms，当时 h1 的路径上没有洪泛），RTT 的最大值要谨慎解读。

同一个 VM 的另外两个目录：
- `results/vm-delay-abc-warmup5/`：默认 warm-up 5，h1 在 +4.3 s 被误封（Phase 3、D14），h1→h6 整场吞吐为 0；s1-s2、s2-s6 一直被标异常，连 case b 的路由也被扭曲（标的是 s2-s3、s3-s6）。**整场无效**，只作为证据保留。它的 `meta.json`（args.out）和 `controller/config.json`（log_dir）里仍写 `results/vm-delay-abc`：目录是跑完之后改名的，`summary.md` 和图是改名后重新生成的。
- `results/miniedit-vm/`：Task 1 的 GUI 搭建与运行，见 Phase 1。

**已完成 / 还剩**（这里原来写的是“在你的虚拟机上要重跑”）：
- ✅ 在官方 Mininet VM（内核 OVS + netem 链路时延）上重跑了 a,b,c：结论与容器一致，RTT 曲线体现了 b 的改路由。
- ✅ Task 1 的截图来自 VM 里的 MiniEdit（见 Phase 1）。
- ⬜ 这个 VM 是纯软件模拟，洪泛速率只有容器的七成左右。在有硬件虚拟化（KVM / VirtualBox / VMware）的 VM 上重跑，攻击者应当能像容器一样打满 40 Mbit/s，case b 的拥塞程度才可比（这一点还没验证）。
- ⬜ 自己手动在 MiniEdit 里画一遍（Phase 1）。
- ⬜ 把 9.2 的结果和新的 Task 1 图写进报告（见第 10 节）。

---

## 10. 已完成的全部运行与报告（2026-10-22 云端容器；2026-11-03 Mininet VM）

| 目录 | 内容 | 结论 |
|---|---|---|
| `results/validation-abc/` (R1) | a,b,c 完整时间线 | 报告主图来源 |
| `results/run1-abc/` (R2)、`results/run2-abc/` (R3) | 重复两次 | 三次结果一致：检测 1.5–3.8 s；只有 b 改路由；恢复在洪泛结束后 13.6–14.9 s |
| `results/exp-beta2-b/`、`results/exp-beta0-b/` | β=2、β=0 | 不改路由，证明 β 必须大于 3+margin |
| `results/exp-c-s5s6-cost8/` | s5–s6 的 C0 改为 8 | h5→h6 走 s5-s6，s5-s6 被标异常；h1 不改路由；h6 接入链路拥塞无法绕开 |
| `results/exp-linkfail-s2s6/` | s2–s6 断开 20 s | 断开瞬间改走 s1-s2-s3-s6，恢复后回切 |
| `results/miniedit-demo/`、`results/manual-demo/` | 容器里的 MiniEdit 运行（加载生成的 `.mn`）、Task 2 CLI 演示的控制台输出 | Task 2 截图在 `report/figures/`；容器版 MiniEdit 截图改名保留为 `results/miniedit-demo/*_container_loaded.png` |
| `results/vm-delay-abc/` | Mininet 2.3.0 VM（QEMU 纯软件模拟）、内核 OVS、netem 链路时延、手动 `CEG_WARMUP=12`，a,b,c | 封禁、异常链路、改路由与 R1–R3 一致；改路由在 RTT 上可见；洪泛较弱、排队时延大（见 9.2） |
| `results/vm-delay-abc-warmup5/` | 同上，但 warm-up 为默认的 5 | h1 被误封，整场无效，只作证据（Phase 3、D14） |
| `results/miniedit-vm/` | VM 里 MiniEdit 的 GUI 搭建与运行：截图 00–09、7 分钟原始录屏 | 报告 Task 1 的两张图来自这里 |

**报告**：最终版是 `report/report.tex` / `report/report.pdf`（16 页）。

- [x] 报告已补上 VM 的内容并重新编译（2026-11-03，16 页）：Environment 段、Task 1 正文和图注、新的 7.4 节“Re-run on the Mininet VM with link delays”（表 5 对比 R1 与 VM、warm-up 误封和自动默认值）、讨论与局限、附录文件表和复现说明；图 1 去掉了旧的 trim，h1 的 iperf 速率改为约 890 pkt/s。

如果你在自己的 VM 上重跑，把报告里的数字换成你的 `summary.md` 即可；结构和分析不用改。


## 11. 演示材料（2026-11-04）

- 幻灯片：`presentation/slides/CEG5101_CA2_Group5.html`（单文件，图片和视频都嵌在里面；浏览器打开，23 页，按 N 看讲稿，按 P 打开演讲者视图；用法见同目录 README.md），讲义 PDF：`presentation/slides/CEG5101_CA2_Group5_handout.pdf`。
- 视频：`presentation/video/demo_case_b.mp4`（第 8 页，case b 真实运行）、`replay_r1.mp4`（第 12 页，R1 回放）、`miniedit_build.mp4`（第 2 页，MiniEdit 搭建）。
- 幻灯片图：`presentation/figures/`；数字口径：`presentation/data/numbers.md`；生成脚本：`presentation/scripts/`。
- 名字已填：A = Yang Kaiming（系统与检测），B = Chen Danze（路由与结果），报告署名、幻灯片第 1 页和第 23 页、讲稿都已更新。到场后在演示电脑的 Chrome/Edge 里试播一次三个视频。
- 现场演示：`bash demo/live_demo.sh`（a、b、c 全跑，约 5–6 分钟）或 `bash demo/live_demo.sh quick`（只跑 b，约 2.5 分钟）。tmux 四格：时间线、控制器状态、控制器事件、h6 收端每秒吞吐和丢包；跑完自动出结果表，`python3 demo/show_figure.py <目录>` 弹总览图。讲解顺序、分工和应急方案见 `docs/Live_Demo_Runbook_zh.pdf`；幻灯片第 7 页切到终端，第 8 页录屏作备用。
- 技术支持：`docs/Tech_Support_Windows_zh.pdf`（VirtualBox + 官方 Mininet VM + MobaXterm）、`docs/Tech_Support_Mac_zh.pdf`（Intel Mac 同 VirtualBox；Apple 芯片用 UTM + Ubuntu 22.04 ARM + apt 装 Mininet）。
