#!/usr/bin/env bash
# Install everything the lab needs on Ubuntu 20.04 / 22.04 / 24.04
# (Mininet VM, a normal Ubuntu VM, or a cloud container running as root).
#
#   bash support/environment/setup_ubuntu.sh            # venv goes to ~/ryu-venv
#   VENV=/opt/ryu bash support/environment/setup_ubuntu.sh
#
# Ryu 4.34 is unmaintained and only installs cleanly on Python <= 3.9 with
# old eventlet/setuptools, so it lives in its own virtualenv.
set -euo pipefail

SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
VENV="${VENV:-$HOME/ryu-venv}"

echo "== apt packages"
$SUDO apt-get update -qq
PKGS="openvswitch-switch hping3 iperf tcpdump ethtool iproute2 iputils-ping python3-tk tmux"
command -v mn >/dev/null 2>&1 || PKGS="$PKGS mininet"     # Mininet VM already has it
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $PKGS

echo "== Python for Ryu"
PY=""
for c in python3.9 python3.8; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
if [ -n "$PY" ]; then
    "$PY" -m venv "$VENV" || { $SUDO apt-get install -y -qq "${PY}-venv"; "$PY" -m venv "$VENV"; }
    "$VENV/bin/pip" install -q "setuptools<58" wheel pbr
    "$VENV/bin/pip" install -q --no-build-isolation "eventlet==0.30.2" "dnspython<2" ryu==4.34 matplotlib
else
    # No old Python on this system: let uv download a 3.9 build.
    command -v uv >/dev/null 2>&1 || { curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }
    uv venv -p 3.9 "$VENV"
    VIRTUAL_ENV="$VENV" uv pip install -q "setuptools<58" wheel pbr
    VIRTUAL_ENV="$VENV" uv pip install -q --no-build-isolation "eventlet==0.30.2" "dnspython<2" ryu==4.34 matplotlib
fi
"$VENV/bin/ryu-manager" --version

echo "== Open vSwitch"
if ! $SUDO ovs-vsctl --timeout=3 show >/dev/null 2>&1; then
    $SUDO service openvswitch-switch start 2>/dev/null || $SUDO /usr/share/openvswitch/scripts/ovs-ctl start --system-id=random
fi
$SUDO ovs-vsctl --timeout=3 show >/dev/null && echo "OVS running"
[ -e /sys/module/openvswitch ] && echo "OVS kernel datapath available" \
    || echo "No OVS kernel module: experiments will use the userspace datapath (--datapath user)"

cat <<MSG

Done. Add to your shell:
    export RYU_MANAGER=$VENV/bin/ryu-manager
    export PLOT_PYTHON=$VENV/bin/python
Then from the project root:
    sudo -E python3 code/experiments/run_experiment.py
MSG
