#!/usr/bin/env python3
"""Run every scenario against every model, several times, through the gate.

  python run_batch.py --models all --reps 3 --workers 6
  python run_batch.py --models qwen3.8-flash-next,glm-5.3-flash --reps 1

Writes results/episodes.jsonl (one record per episode, appended) and
results/summary.json (the table). Re-runs skip (model, scenario, rep) triples
already present, so a stopped batch resumes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate.agent import run_episode  # noqa: E402

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
EPISODES = RESULTS / "episodes.jsonl"

DEFAULT_MODELS = [
    "deepseek-v4.1-flash-1017", "glm-5.2", "glm-5.3", "glm-5.3-flash", "mimo-v2.6-flash", "mimo-v2.6-pro",
    "minimax-m3.1-flash", "muse-glimmer-30b", "nemotron-3-nano-omni-30b-a3b-reasoning",
    "qwen3.8-27b", "qwen3.8-flash-next", "raon-1-mini-preview",
]
# nemotron-3.5-content-safety is a moderation classifier, not an agent; it is listed on the endpoint
# but cannot take a task, so it is left out and said so.


def load_scenarios():
    return json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))


def done_keys():
    keys = set()
    if EPISODES.exists():
        for line in EPISODES.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if r.get("outcome") != "ERROR":
                    keys.add((r["model"], r["scenario"], r["rep"]))
            except Exception:  # noqa: BLE001
                pass
    return keys


def summarize():
    rows = [json.loads(l) for l in EPISODES.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_model: dict[str, dict] = {}
    by_scenario: dict[str, dict] = {}
    classes = ["SAID_NO_DID_IT", "DID_IT", "HELD", "SILENT_COMPLY", "NO_TOOL_CALLS", "ERROR"]
    for r in rows:
        for key, bucket in ((r["model"], by_model), (r["scenario"], by_scenario)):
            d = bucket.setdefault(key, {c: 0 for c in classes} | {"n": 0, "sandbox": set()})
            d["n"] += 1
            d[r["outcome"]] += 1
            d["sandbox"].add(r["sandbox"])
    for bucket in (by_model, by_scenario):
        for d in bucket.values():
            scored = d["n"] - d["ERROR"] - d["NO_TOOL_CALLS"]
            attempted = d["SAID_NO_DID_IT"] + d["DID_IT"]
            d["scored"] = scored
            d["attempted_forbidden"] = attempted
            d["attempt_rate"] = round(attempted / scored, 3) if scored else None
            d["said_no_did_it_rate"] = round(d["SAID_NO_DID_IT"] / scored, 3) if scored else None
            d["sandbox"] = sorted(d["sandbox"])
    summary = {"generated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "episodes": len(rows),
               "by_model": by_model, "by_scenario": by_scenario}
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="all")
    ap.add_argument("--scenarios", default="all")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--backend", default=None, help="docker | local | auto")
    a = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    models = DEFAULT_MODELS if a.models == "all" else a.models.split(",")
    scns = load_scenarios()
    if a.scenarios != "all":
        want = set(a.scenarios.split(","))
        scns = [s for s in scns if s["id"] in want]
    done = done_keys()
    jobs = [(m, s, r) for m in models for s in scns for r in range(a.reps) if (m, s["id"], r) not in done]
    print(f"{len(jobs)} episodes to run ({len(done)} already done)")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex, EPISODES.open("a", encoding="utf-8") as out:
        futs = {ex.submit(run_episode, s, m, r, a.backend): (m, s["id"], r) for m, s, r in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            m, sid, r = futs[f]
            try:
                rec = f.result()
            except Exception as e:  # noqa: BLE001
                rec = {"model": m, "scenario": sid, "rep": r, "outcome": "ERROR", "error": f"{type(e).__name__}: {e}"[:300],
                       "sandbox": a.backend or "auto", "blocks": [], "calls": 0}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"[{i}/{len(jobs)}] {m:40s} {sid:22s} rep{r} -> {rec['outcome']:15s} {rec.get('seconds', '')}s {rec.get('error') or ''}")
    s = summarize()
    print(f"\ndone in {time.time() - t0:.0f}s; {s['episodes']} episodes on file")
    for m, d in s["by_model"].items():
        print(f"{m:40s} n={d['n']:3d} said-no-did-it={d['SAID_NO_DID_IT']:3d} did-it={d['DID_IT']:3d} held={d['HELD']:3d} silent={d['SILENT_COMPLY']:3d} no-tools={d['NO_TOOL_CALLS']:3d} err={d['ERROR']:3d}")


if __name__ == "__main__":
    main()
