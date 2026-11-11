# Code and reproduction

## Quick start

Run these commands from the project root, `ceg5101-sdn-lab/`. Run the setup script once on a fresh Mininet VM.

```bash
bash support/environment/setup_ubuntu.sh
export RYU_MANAGER=~/ryu-venv/bin/ryu-manager PLOT_PYTHON=~/ryu-venv/bin/python
sudo -E python3 code/experiments/run_experiment.py
```

The full run writes logs to `results/<timestamp>/` and calls the plotter in `support/analysis/`. For the live presentation, use `bash code/demo/live_demo.sh` in place of the last command. Add `quick` for the shorter demo.

Tested in a cloud container (Ubuntu 24.04, userspace OVS, no link delays, runs R1–R3 in `results/validation-abc/`, `run1-abc/`, `run2-abc/`) and in the official Mininet 2.3.0 VM (Ubuntu 20.04, kernel OVS 2.13, netem link delays, `results/vm-delay-abc/`). That VM used QEMU software emulation without hardware acceleration, which affected traffic rates. See the [report](../report/report.pdf), §7.4, for the VM results.

With link delays, `run_experiment.py` sets `CEG_WARMUP=12` itself when it starts the controller and `CEG_WARMUP` is not set. With the 5-sample default, h1's own iperf started after its warm-up and h1 was blocked (`results/vm-delay-abc-warmup5/`, kept as evidence, not a valid result). To override: `sudo -E env CEG_WARMUP=N python3 code/experiments/run_experiment.py`.

Controller only (for MiniEdit or a manual `mn` session):

```bash
CEG_LOG_DIR=results/manual/controller $RYU_MANAGER --observe-links code/controller/integrated_controller.py
```

If you use it with `run_experiment.py --controller external` on a network with link delays, also start it with `CEG_WARMUP=12` (the runner cannot change a controller that is already running).

## MiniEdit (Task 1)

The topology was built and run in the MiniEdit GUI in the Mininet 2.3.0 VM. Open `code/miniedit/my_topology.mn` in MiniEdit. Its links and host IPs match `code/topology/ceg_mesh_topo.py`. The screenshots are in `report/source/figures/task1_miniedit_*.png`. [The archived plan](../../archive/PLAN.md) records the build steps in Phase 1.

MiniEdit as shipped with Mininet 2.3.0 cannot save under Python 3: File > Save and Export open the file with `'wb'` and write a `str`, leaving a 0-byte file. Fix (2 lines; patch the installed copy under `/usr/local/lib/python3.8/dist-packages/mininet/examples/` too if that is the one you start):

```bash
sudo sed -i.orig "s/open(fileName, 'wb')/open(fileName, 'w')/" ~/mininet/examples/miniedit.py
```

For the current demo command and keyboard shortcuts, see the [presentation guide](../presentation/README.md).

## Optional checks

```bash
python3 -m unittest discover -s support/tests
python3 support/analysis/expected_paths.py
```
