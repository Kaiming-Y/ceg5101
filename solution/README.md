# CEG5101 CA2 · 任务与 11 月 12 日展示

先读这一页，再看[中文速读](ceg5101-sdn-lab/docs/Project_Quick_Guide_zh.pdf)第 1–3 节。做展示准备直接开[幻灯片](ceg5101-sdn-lab/presentation/source/CEG5101_CA2_Group5_light.html)和[英文讲稿](ceg5101-sdn-lab/presentation/speaker_script.pdf)。

## 老师要我们完成什么

在给定的 6 台交换机 mesh 上实现一个 Ryu 控制器。它要识别异常流量并按源 IP 封禁，同时根据实时负载和异常状态调整链路代价，让正常的 h1→h6 流量在需要时绕行，异常消退后恢复。老师按概念理解、设计推理、结果解读评分。[官方题目](../problem/assignment/Lab%20Assignment.pdf)

| 任务 | 要解决的问题 | 现有证据 |
| --- | --- | --- |
| 1 · MiniEdit，5 分 | 用给定的拓扑在 MiniEdit 里搭建并运行。 | [MiniEdit 拓扑](ceg5101-sdn-lab/code/miniedit/my_topology.mn)、[运行截图](ceg5101-sdn-lab/report/source/figures/task1_miniedit_running.png)、S2。 |
| 2 · 检测与封禁，5 分 | 用正常 ping 建立 EMA 基线，识别异常源，验证按源 IP 下发的 drop 规则确实停止转发异常流量。 | S3–S4、S8–S9、[封禁证据图](ceg5101-sdn-lab/report/source/figures/fig5_blocking.png)。 |
| 3 · 动态链路代价，10 分 | 用原始代价、实时负载和异常标记给交换机间链路定价。要能解释封禁后负载下降，为什么受影响链路仍然维持较高代价。 | S5、[归一化代价图](ceg5101-sdn-lab/report/source/figures/fig1_link_cost.png)。 |
| 4 · 合法流量改路与恢复，10 分 | 先建立 h1→h6，再依次检查 a、b、c。对每例记录路径、代价、丢包和吞吐，验证封禁、连通性及恢复。 | S6–S12、[三例结果](ceg5101-sdn-lab/results/validation-abc/summary.md)、[case c 指定链路验证](ceg5101-sdn-lab/results/exp-c-s5s6-cost8/summary.md)。 |
| 5 · 性能评估 | 报告放拓扑截图，画归一化代价、丢包率、吞吐对时间的三张图，解释异常前、期间和之后的变化。题目未单列分值。 | S11 和[报告](ceg5101-sdn-lab/report/report.pdf)第 6 节。 |

### 上台前能讲清的三件事

1. **控制器做了什么。** 每轮用 FlowStats 看入口源速率，用 PortStats 看链路负载。源速率超过 EMA 自适应阈值就下发 drop，并标记该源走过的链路。动态代价为 `C₀ + α·R/Rmax + β·A`，Dijkstra 比较路径，备选路明显更便宜才切换。
2. **为什么只有 case b 绕行。** 正常走 `s1–s2–s6`，a 占用 `s2–s3`，b 占用正常路径上的 `s2–s6`，因此 b 绕到 `s1–s2–s3–s6`，随后回切。c 的默认路由走 `s5–s3–s6`（16 < 20），所以另做了将直连代价从 20 降至 8 的实验，确认异常标记确实出现在题目指定的 `s5–s6`。两种 c 都保持 h1→h6 原路。需要解释 c 的丢包时，指出两路流量仍共用 h6 的接入链路。
3. **哪一步带来哪种效果。** R1 的 case b 在检测前最坏一秒丢包 48.4%，封禁后恢复到 0%。封禁停止异常转发，异常惩罚项让合法流量继续避开该链路。R1–R3 的检测耗时 1.5–3.8 秒，case b 在异常流量结束约 14 秒后回切。48.4% 是单秒峰值。[数字出处](ceg5101-sdn-lab/presentation/source/numbers.md)

## 明天先准备这些

1. **幻灯片与讲稿。** 按讲稿的 S1–S14 跑一次约 12 分钟的录像版。讲稿标注 11 月 12 日 10:25–10:50，SDE1-SR1。Kaiming 主要讲拓扑、检测和封禁，Danze 主要讲代价、改路与结果。现场模式和正式时长以 GA 通知为准，S23 的贡献表述由两人按实际分工核对。
2. **演示切换。** 在展示电脑上用 Chrome 或 Edge 试 S2、S8、S12 的视频，试按数字加 Enter 跳到 S15、S16 的静态备用页。S7 是现场切换点。若确认现场演示，按[现场手册](ceg5101-sdn-lab/presentation/Live_Demo_Runbook_zh.pdf)彩排并重算时间，手册里的完整版约 5–6 分钟，讲稿的录像版已经排满 12 分钟。S17–S23 留给问答，重点看 S20（case c）、S22（代码地图）、S23（分工与工具）。
3. **报告和代码备查。** [报告 PDF](ceg5101-sdn-lab/report/report.pdf)重点看第 3、5、6 节和第 7.2 节。准备好定位下面两份控制器代码，以及 Task 1 的 MiniEdit 文件。

## 代码、报告和材料从哪找

| 优先级 | 文件 | 需要掌握到什么程度 |
| --- | --- | --- |
| 核心代码 | [integrated_controller.py](ceg5101-sdn-lab/code/controller/integrated_controller.py)、[sdn_logic.py](ceg5101-sdn-lab/code/controller/sdn_logic.py) | 能沿 `_monitor → _evaluate → _block / _reroute_all` 讲运行链，能定位 `AnomalyDetector`、`dynamic_cost`、`dijkstra`。 |
| 必需拓扑 | [ceg_mesh_topo.py](ceg5101-sdn-lab/code/topology/ceg_mesh_topo.py)、[my_topology.mn](ceg5101-sdn-lab/code/miniedit/my_topology.mn) | 前者是老师给的拓扑，也是实验输入。后者是 Task 1 从 MiniEdit GUI 保存的交付物。知道两者对应同一张图。 |
| 复现实验与出图 | [run_experiment.py](ceg5101-sdn-lab/code/experiments/run_experiment.py)、[plot_results.py](ceg5101-sdn-lab/support/analysis/plot_results.py) | 知道前者负责时间线与采集，后者用日志生成报告图表。复现或问到数据口径时再读。 |
| 现场展示工具 | [code/demo/](ceg5101-sdn-lab/code/demo/)、[环境安装](ceg5101-sdn-lab/support/environment/setup_ubuntu.sh) | 负责现场的同学看手册和入口即可。看板脚本与安装细节可跳过。 |
| 可跳过的辅助代码 | [support/tests/](ceg5101-sdn-lab/support/tests/)、[expected_paths.py](ceg5101-sdn-lab/support/analysis/expected_paths.py)、[MiniEdit 辅助文件](ceg5101-sdn-lab/code/miniedit/)、[幻灯片制作脚本](ceg5101-sdn-lab/support/presentation/)、[QEMU 启动脚本](ceg5101-sdn-lab/support/environment/qemu_mininet_vm.sh) | 分别用于单元测试、理论路径核对、拓扑转换或导出、生成图与回放、启动特定 VM。 |
| 报告 | [report/](ceg5101-sdn-lab/report/) | PDF 是阅读版，LaTeX 和图源用于修改。 |
| 展示与文档 | [presentation/](ceg5101-sdn-lab/presentation/)、[docs/](ceg5101-sdn-lab/docs/) | 幻灯片 HTML、讲稿 PDF、[讲义 PDF](ceg5101-sdn-lab/presentation/CEG5101_CA2_Group5_handout.pdf)是演示材料。[中文精简报告](ceg5101-sdn-lab/docs/Lab_Quick_Report_zh.pdf)供组内理解图表，[Q&A](ceg5101-sdn-lab/docs/QA_Bank.pdf)按题查，技术支持遇到环境问题再看。 |
| 证据与历史 | [results/](ceg5101-sdn-lab/results/)、[archive/](archive/) | 平时查 `summary.md` 即可。原始 CSV、日志、重复运行、扩展实验、旧计划、模板和参考副本可先跳过。`vm-delay-abc-warmup5` 是误封 h1 的失败运行，仅用于说明局限。 |

[项目目录](ceg5101-sdn-lab/README.md)按代码、展示、组内文档、报告、实验结果导航。复现命令见[代码运行说明](ceg5101-sdn-lab/docs/Run_Lab.md)。
