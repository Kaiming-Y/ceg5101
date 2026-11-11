# CEG5101 CA2 · 项目目录

任务要求和展示顺序见[作业总览](../README.md)。

| 目录 | 放什么 | 先打开 |
| --- | --- | --- |
| [`code/`](code/) | 运行 Lab 和现场展示用的文件。包括控制器、Python 和 MiniEdit 拓扑、实验入口、现场看板。 | [运行说明](docs/Run_Lab.md) |
| [`presentation/`](presentation/) | 上台用的幻灯片、讲稿、讲义和现场演示手册。视频和图片在 `assets/`，幻灯片 HTML 在 `source/`。 | [幻灯片](presentation/source/CEG5101_CA2_Group5_light.html) · [讲稿](presentation/speaker_script.pdf) · [演示操作](presentation/README.md) |
| [`docs/`](docs/) | 组内阅读的中文速读、中文精简报告、Q&A。环境配置在 `environment/`，文档源文件在 `source/`。 | [中文速读](docs/Project_Quick_Guide_zh.pdf) · [Q&A](docs/QA_Bank.pdf) |
| [`report/`](report/) | 正式英文报告。LaTeX 和编译所需图片在 `source/`。 | [正式报告](report/report.pdf) |
| [`results/`](results/) | 每次运行的原始数据、日志、图表和汇总。 | [主实验 R1](results/validation-abc/summary.md) · [case c 指定链路验证](results/exp-c-s5s6-cost8/summary.md) |
| [`support/`](support/) | 测试、数据分析和出图、幻灯片素材生成、MiniEdit 辅助文件、环境安装。实验结束后由运行脚本自动调用出图工具。 | 准备展示时可跳过 |

上台前先看 `presentation/`。准备解释实现时，读 `code/controller/` 的两份 Python 文件，了解 `code/miniedit/my_topology.mn` 和题目拓扑的对应关系。其他代码按复现、排错或修改的需要查阅。

已有 PDF 中的路径沿用原目录。当前命令见[运行说明](docs/Run_Lab.md)和[演示操作](presentation/README.md)。旧计划见[上一级归档](../archive/)。
