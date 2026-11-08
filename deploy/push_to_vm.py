#!/usr/bin/env python3
"""Push this project to the Vultr VM and set it up, from a laptop without ssh keys on the box yet.

  set SAYDO_VM_HOST=1.2.3.4
  set SAYDO_VM_PASS=<root password from the Vultr page>   (first run only; installs ~/.ssh/id_ed25519.pub)
  python deploy/push_to_vm.py            # upload + setup + start the service
  python deploy/push_to_vm.py --run "cd /opt/saydo-gate && .venv/bin/python run_batch.py --reps 1"

Secrets: the inference key is read from ~/.vultr_inference_key on the laptop and written to
/etc/saydo-gate.env on the VM (mode 600). Nothing is printed.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import tarfile
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {".git", ".venv", "__pycache__", "results_local", "media", "uvicorn_local.log", ".env"}


def connect(host: str) -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = Path.home() / ".ssh" / "id_ed25519"
    pw = os.environ.get("SAYDO_VM_PASS")
    last = None
    for attempt in range(12):
        try:
            if pw:
                c.connect(host, username="root", password=pw, timeout=20, look_for_keys=False, allow_agent=False)
            else:
                c.connect(host, username="root", key_filename=str(key_path), timeout=20)
            return c
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  connect attempt {attempt + 1} failed: {type(e).__name__}; retrying in 10 s")
            time.sleep(10)
    raise SystemExit(f"could not connect: {last}")


def run(c: paramiko.SSHClient, cmd: str, quiet: bool = False) -> str:
    _, out, err = c.exec_command(cmd, get_pty=True)
    text = out.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    if not quiet:
        print(text[-4000:])
    if code != 0:
        print(f"  [exit {code}] {cmd[:80]}")
    return text


def tar_project() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for p in ROOT.rglob("*"):
            rel = p.relative_to(ROOT)
            if any(part in EXCLUDE for part in rel.parts):
                continue
            if p.is_file():
                tf.add(p, arcname=str(rel).replace("\\", "/"))
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="only run this command on the VM")
    ap.add_argument("--no-setup", action="store_true")
    a = ap.parse_args()
    host = os.environ["SAYDO_VM_HOST"]
    c = connect(host)
    if a.run:
        run(c, a.run)
        return
    # 1. install our public key so later connections need no password
    pub = (Path.home() / ".ssh" / "id_ed25519.pub").read_text().strip()
    run(c, f"mkdir -p ~/.ssh && grep -qF '{pub.split()[1]}' ~/.ssh/authorized_keys 2>/dev/null || echo '{pub}' >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys", quiet=True)
    # 2. upload the project
    data = tar_project()
    sftp = c.open_sftp()
    with sftp.file("/root/saydo-gate.tgz", "wb") as f:
        f.write(data)
    sftp.close()
    run(c, "mkdir -p /opt/saydo-gate && tar xzf /root/saydo-gate.tgz -C /opt/saydo-gate && ls /opt/saydo-gate")
    # 3. the inference key, host side only
    key = (Path.home() / ".vultr_inference_key").read_text().strip()
    run(c, f"umask 077; printf 'VULTR_INFERENCE_KEY={key}\\nSAYDO_SANDBOX=docker\\n' > /etc/saydo-gate.env; chmod 600 /etc/saydo-gate.env", quiet=True)
    if not a.no_setup:
        run(c, "bash /opt/saydo-gate/deploy/setup_vm.sh")
    run(c, "systemctl restart saydo-gate && sleep 3 && systemctl is-active saydo-gate && curl -s -o /dev/null -w 'http %{http_code}\\n' http://127.0.0.1/")
    print(f"done. app: http://{host}/")


if __name__ == "__main__":
    main()
