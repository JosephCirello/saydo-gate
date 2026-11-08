"""The sandbox: one throwaway box per episode.

Two backends with the same interface:

  DockerSandbox  - the real thing, used on the Vultr VM. One container per
                   episode from python:3.12-slim: --network none, memory and
                   CPU caps, a PID limit, no host mounts, destroyed after.
  LocalSandbox   - a temp directory on the host, for development on a laptop
                   without Docker. Same tools, same file layout, no isolation.
                   Results produced this way are labelled "local" in the record.

Secret hygiene: the model API key never enters either sandbox. The sandbox
only ever sees tools.py, the scenario fixtures and what the agent writes.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS_PY = HERE.parent / "sandbox" / "tools.py"


def _write_fixtures(root: Path, fixtures: dict) -> None:
    (root / "state").mkdir(parents=True, exist_ok=True)
    (root / "state" / "inbox.json").write_text(json.dumps(fixtures.get("inbox", []), indent=1), encoding="utf-8")
    for rel, content in fixtures.get("files", {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


class LocalSandbox:
    kind = "local"

    def __init__(self, fixtures: dict):
        self.root = Path(tempfile.mkdtemp(prefix="saydo_"))
        _write_fixtures(self.root, fixtures)

    def call(self, tool: str, args: dict) -> dict:
        env = dict(os.environ, SAYDO_WORK=str(self.root))
        r = subprocess.run([sys.executable, "-I", str(TOOLS_PY), tool, json.dumps(args)],
                           capture_output=True, text=True, timeout=60, env=env, cwd=str(self.root))
        return _parse(r.stdout, r.stderr)

    def destroy(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


class DockerSandbox:
    kind = "docker"
    IMAGE = os.environ.get("SAYDO_IMAGE", "python:3.12-slim")

    def __init__(self, fixtures: dict):
        self.name = f"saydo-{uuid.uuid4().hex[:12]}"
        staging = Path(tempfile.mkdtemp(prefix="saydo_stage_"))
        _write_fixtures(staging / "work", fixtures)
        shutil.copy(TOOLS_PY, staging / "tools.py")
        subprocess.run([
            "docker", "create", "--name", self.name,
            "--network", "none",            # no network: nothing leaves the box
            "--memory", "256m", "--cpus", "0.5", "--pids-limit", "64",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp:size=64m",
            "-v", f"{self.name}-work:/work",   # a named volume that dies with the box
            self.IMAGE, "sleep", "600",         # the box lives at most ten minutes
        ], check=True, capture_output=True)
        subprocess.run(["docker", "cp", str(staging / "work") + "/.", f"{self.name}:/work/"], check=True, capture_output=True)
        subprocess.run(["docker", "cp", str(staging / "tools.py"), f"{self.name}:/work/tools.py"], check=True, capture_output=True)
        subprocess.run(["docker", "start", self.name], check=True, capture_output=True)
        shutil.rmtree(staging, ignore_errors=True)

    def call(self, tool: str, args: dict) -> dict:
        r = subprocess.run(["docker", "exec", "-e", "SAYDO_WORK=/work", self.name,
                            "python3", "-I", "/work/tools.py", tool, json.dumps(args)],
                           capture_output=True, text=True, timeout=60)
        return _parse(r.stdout, r.stderr)

    def destroy(self) -> None:
        subprocess.run(["docker", "rm", "-f", "-v", self.name], capture_output=True)


def _parse(stdout: str, stderr: str) -> dict:
    try:
        return json.loads(stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": "tool produced no result", "stderr": stderr[-500:]}


def make_sandbox(fixtures: dict, backend: str | None = None):
    backend = backend or os.environ.get("SAYDO_SANDBOX", "auto")
    if backend == "auto":
        backend = "docker" if shutil.which("docker") else "local"
    return DockerSandbox(fixtures) if backend == "docker" else LocalSandbox(fixtures)
