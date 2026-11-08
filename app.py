#!/usr/bin/env python3
"""The web app: pick a scenario and a model, watch the agent work in a fresh sandbox,
and watch the gate block the forbidden action. Plus the results table from the batch.

  uvicorn app:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from gate.agent import run_episode
from run_batch import DEFAULT_MODELS

ROOT = Path(__file__).resolve().parent
SCENARIOS = json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))
BY_ID = {s["id"]: s for s in SCENARIOS}
app = FastAPI(title="Say-vs-Do Gate")


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/scenarios")
def scenarios():
    return [{"id": s["id"], "title": s["title"], "domain": s["domain"], "policy": s["policy"], "task": s["task"], "pressure": s["pressure"]} for s in SCENARIOS]


@app.get("/api/models")
def models():
    return DEFAULT_MODELS


@app.get("/api/results")
def results():
    p = ROOT / "results" / "summary.json"
    if not p.exists():
        return JSONResponse({"episodes": 0, "by_model": {}, "by_scenario": {}})
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/episodes")
def episodes(model: str | None = None, scenario: str | None = None, limit: int = 50):
    p = ROOT / "results" / "episodes.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if model and r.get("model") != model:
            continue
        if scenario and r.get("scenario") != scenario:
            continue
        out.append({k: r.get(k) for k in ("model", "scenario", "rep", "outcome", "blocks", "said_markers", "final_report", "report_mentions_block", "sandbox", "seconds", "transcript")})
    return out[-limit:]


@app.get("/api/run")
def run(scenario: str, model: str):
    """Server-sent events: one JSON event per line of the episode."""
    scn = BY_ID[scenario]
    q: queue.Queue = queue.Queue()

    def work():
        try:
            rec = run_episode(scn, model, rep=0, on_event=q.put)
            q.put({"type": "done", "outcome": rec["outcome"], "final_report": rec["final_report"], "seconds": rec["seconds"], "sandbox": rec["sandbox"]})
        except Exception as e:  # noqa: BLE001
            q.put({"type": "error", "msg": f"{type(e).__name__}: {e}"[:300]})
            q.put({"type": "done", "outcome": "ERROR"})
        q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def gen():
        while True:
            ev = q.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
