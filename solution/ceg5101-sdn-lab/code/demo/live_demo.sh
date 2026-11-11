#!/usr/bin/env bash
# Live demo: run the experiment and watch it in four panes.
#
#   bash code/demo/live_demo.sh            full run: cases a, b, c  (about 5-6 minutes)
#   bash code/demo/live_demo.sh quick      case b only              (about 2.5 minutes)
#
# Panes:  top-left  experiment timeline      top-right  controller state (path, link costs, sources)
#         bottom-left controller events      bottom-right h1->h6 at the receiver (per second)
# Leave with Ctrl-b d (detach) or close the terminal; 'sudo mn -c' cleans up after an aborted run.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then exec sudo -E bash "$0" "$@"; fi
cd "$(dirname "$0")/../.."

USER_HOME=$(getent passwd "${SUDO_USER:-$(id -un)}" | cut -d: -f6)
export RYU_MANAGER=${RYU_MANAGER:-$USER_HOME/ryu-venv/bin/ryu-manager}
export PLOT_PYTHON=${PLOT_PYTHON:-$USER_HOME/ryu-venv/bin/python}
export XAUTHORITY=${XAUTHORITY:-$USER_HOME/.Xauthority}
[ -x "$RYU_MANAGER" ] || { echo "ryu-manager not found at $RYU_MANAGER (run support/environment/setup_ubuntu.sh)"; exit 1; }
command -v tmux >/dev/null || { echo "tmux missing: sudo apt install -y tmux"; exit 1; }

MODE=${1:-full}
case "$MODE" in
  full)  ARGS="" ;;
  quick) ARGS="--scenarios b --baseline 30 --recover 40" ;;
  *)     echo "usage: $0 [full|quick]"; exit 1 ;;
esac
OUT=results/live-$(date +%m%d-%H%M%S)
mkdir -p "$OUT"
mn -c >/dev/null 2>&1 || true

S=cegdemo
tmux kill-session -t $S 2>/dev/null || true
RUN="python3 code/experiments/run_experiment.py --out $OUT $ARGS 2>&1 \
 | grep --line-buffered -E '^\*\*\* (\[|datapath|link delays|Results)|Traceback|Exception'; \
 python3 code/demo/show_summary.py $OUT; \
 echo; echo 'Overview figure:  python3 code/demo/show_figure.py $OUT   (Esc closes it)'; exec bash"
if [ -t 1 ]; then W=$(tput cols); H=$(tput lines); else W=200; H=50; fi
P0=$(tmux new-session -d -s $S -x "$W" -y "$H" -P -F '#{pane_id}' "bash -c \"$RUN\"")
P1=$(tmux split-window -h -t "$P0" -P -F '#{pane_id}' "python3 code/demo/watch_state.py $OUT; exec bash")
split() {   # tmux >= 3.1 takes -l N%, tmux 3.0 (Ubuntu 20.04 / Mininet VM) takes -p N
  local target=$1 pct=$2; shift 2
  tmux split-window -v -t "$target" -l "$pct%" "$@" 2>/dev/null || tmux split-window -v -t "$target" -p "$pct" "$@"
}
split "$P0" 65 "python3 code/demo/watch_events.py $OUT"
split "$P1" 45 "python3 code/demo/watch_iperf.py $OUT"
tmux set -t $S mouse on >/dev/null
tmux set -t $S pane-border-status top >/dev/null 2>&1 || true
tmux select-pane -t "$P0"
echo "results go to $OUT"
if [ -t 0 ] && [ -t 1 ]; then tmux attach -t $S; else echo "started tmux session $S (attach with: sudo tmux attach -t $S)"; fi
