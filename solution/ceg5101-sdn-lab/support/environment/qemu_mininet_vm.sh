#!/usr/bin/env bash
# Boot the official Mininet 2.3.0 VM image (Ubuntu 20.04, kernel OVS, sch_netem) under QEMU.
# Used to re-run the experiment with real link delays from a cloud container that has no
# KVM, no OVS kernel module and no sch_netem. Pure software emulation (TCG) is slow: the
# attacker sends only ~3-4k pkt/s and about 70% of the container flood rate reaches the victim,
# so loss figures differ from a real VM (see report, Section 7, 'Re-run on the Mininet VM').
set -euo pipefail
DIR=${1:-$HOME/mininet-vm}; mkdir -p "$DIR"; cd "$DIR"
[ -f mininet-vm-x86_64.vmdk ] || {
  curl -L -o mininet-vm.zip https://github.com/mininet/mininet/releases/download/2.3.0/mininet-2.3.0-210211-ubuntu-20.04.1-legacy-server-amd64-ovf.zip
  unzip -o mininet-vm.zip; }
[ -f overlay.qcow2 ] || qemu-img create -f qcow2 -b mininet-vm-x86_64.vmdk -F vmdk overlay.qcow2 20G
ACCEL=tcg,thread=multi; [ -e /dev/kvm ] && ACCEL=kvm
qemu-system-x86_64 -machine pc -accel $ACCEL -cpu max -smp 4 -m 4096 \
  -drive file=overlay.qcow2,if=virtio,format=qcow2 \
  -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22 \
  -display none -monitor unix:mon.sock,server,nowait -serial file:serial.log -daemonize -pidfile qemu.pid
echo "VM booting; login: ssh -p 2222 mininet@127.0.0.1 (password mininet), then:"
echo "  bash support/environment/setup_ubuntu.sh && sudo -E python3 code/experiments/run_experiment.py"
