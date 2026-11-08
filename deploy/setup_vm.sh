#!/bin/bash
# One-shot setup for a fresh Ubuntu 24.04 Vultr instance. Run as root.
#   bash setup_vm.sh
set -euo pipefail
apt-get update -y
apt-get install -y docker.io python3-venv python3-pip git
systemctl enable --now docker
docker pull python:3.12-slim
mkdir -p /opt/saydo-gate
cd /opt/saydo-gate
if [ ! -d .git ]; then git clone https://github.com/JosephCirello/saydo-gate.git . 2>/dev/null || true; fi
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
cat >/etc/systemd/system/saydo-gate.service <<'UNIT'
[Unit]
Description=Say-vs-Do Gate (Vultr Agent Rush)
After=network.target docker.service

[Service]
WorkingDirectory=/opt/saydo-gate
EnvironmentFile=/etc/saydo-gate.env
ExecStart=/opt/saydo-gate/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 80
Restart=always

[Install]
WantedBy=multi-user.target
UNIT
touch /etc/saydo-gate.env
chmod 600 /etc/saydo-gate.env
systemctl daemon-reload
systemctl enable saydo-gate
echo "setup done. Put VULTR_INFERENCE_KEY=... in /etc/saydo-gate.env then: systemctl restart saydo-gate"
