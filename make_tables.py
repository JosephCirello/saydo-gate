#!/usr/bin/env python3
"""Print the results tables as Markdown from results/summary.json, for the README and the submission.
  python make_tables.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
S = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
SCN = {s["id"]: s for s in json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))}


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "n/a"


print(f"_{S['episodes']} episodes, generated {S['generated']}._\n")
print("### By model\n")
print("| Model | Scored | Said no, did it | Did it | Attempted forbidden | Held, said why | Held, silent | No tool calls | Errors |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for m, d in sorted(S["by_model"].items(), key=lambda kv: (-(kv[1]["attempted_forbidden"]), kv[0])):
    print(f"| {m} | {d['scored']} | {d['SAID_NO_DID_IT']} | {d['DID_IT']} | {d['attempted_forbidden']} ({pct(d['attempted_forbidden'], d['scored'])}) | {d['HELD']} | {d['SILENT_COMPLY']} | {d['NO_TOOL_CALLS']} | {d['ERROR']} |")
tot = {k: sum(d[k] for d in S["by_model"].values()) for k in ("scored", "SAID_NO_DID_IT", "DID_IT", "attempted_forbidden", "HELD", "SILENT_COMPLY", "NO_TOOL_CALLS", "ERROR")}
print(f"| **All** | {tot['scored']} | {tot['SAID_NO_DID_IT']} | {tot['DID_IT']} | {tot['attempted_forbidden']} ({pct(tot['attempted_forbidden'], tot['scored'])}) | {tot['HELD']} | {tot['SILENT_COMPLY']} | {tot['NO_TOOL_CALLS']} | {tot['ERROR']} |")
print("\n### By scenario\n")
print("| Scenario | Pressure | Scored | Said no, did it | Did it | Attempted | Held, said why | Held, silent |")
print("|---|---|---:|---:|---:|---:|---:|---:|")
for s, d in sorted(S["by_scenario"].items(), key=lambda kv: (-(kv[1]["attempted_forbidden"]), kv[0])):
    sc = SCN.get(s, {"title": s, "pressure": ""})
    print(f"| {sc['title']} | {sc['pressure']} | {d['scored']} | {d['SAID_NO_DID_IT']} | {d['DID_IT']} | {d['attempted_forbidden']} | {d['HELD']} | {d['SILENT_COMPLY']} |")
sb = sorted({x for d in S["by_model"].values() for x in d["sandbox"]})
print(f"\nSandbox backend on these episodes: {', '.join(sb)}.")
