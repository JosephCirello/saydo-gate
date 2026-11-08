#!/usr/bin/env python3
"""Compare two passes of the same scenarios and models, hours apart, from results/episodes.jsonl.
Pass 1 = reps 0..2, pass 2 = reps 3..5. Prints Markdown. Nothing typed by hand.
  python compare_passes.py
"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rows = [json.loads(l) for l in (ROOT / "results" / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
SCN = {s["id"]: s for s in json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))}
ATT = ("SAID_NO_DID_IT", "DID_IT")


def window(rs):
    ts = sorted(r["ts"] for r in rs)
    return f"{ts[0][11:16]} to {ts[-1][11:16]} UTC" if ts else "n/a"


p1 = [r for r in rows if r["rep"] < 3]
p2 = [r for r in rows if r["rep"] >= 3]
print(f"_Pass 1: {len(p1)} episodes, {window(p1)}. Pass 2: {len(p2)} episodes, {window(p2)}. Same ten scenarios, same twelve models, temperature 0, three runs each per pass._\n")


def tally(rs, key):
    d = collections.defaultdict(lambda: {"n": 0, "att": 0, "sn": 0, "held": 0, "silent": 0, "err": 0})
    for r in rs:
        k = r[key]; d[k]["n"] += 1
        if r["outcome"] in ATT: d[k]["att"] += 1
        if r["outcome"] == "SAID_NO_DID_IT": d[k]["sn"] += 1
        if r["outcome"] == "HELD": d[k]["held"] += 1
        if r["outcome"] == "SILENT_COMPLY": d[k]["silent"] += 1
        if r["outcome"] == "ERROR": d[k]["err"] += 1
    return d


def totals(rs):
    t = tally(rs, "model"); return {k: sum(v[k] for v in t.values()) for k in ("n", "att", "sn", "held", "silent", "err")}


t1, t2 = totals(p1), totals(p2)
print("### Totals\n")
print("| | Pass 1 | Pass 2 | Change |")
print("|---|---:|---:|---:|")
for label, k in (("Scored episodes", "n"), ("Forbidden action attempted (all blocked)", "att"), ("Said no, then did it", "sn"), ("Held, said why", "held"), ("Held, silent", "silent"), ("Errors", "err")):
    print(f"| {label} | {t1[k]} | {t2[k]} | {t2[k] - t1[k]:+d} |")

print("\n### By model: forbidden action attempted (of 30 per pass)\n")
print("| Model | Pass 1 | Pass 2 | Change | Silent, pass 1 | Silent, pass 2 |")
print("|---|---:|---:|---:|---:|---:|")
m1, m2 = tally(p1, "model"), tally(p2, "model")
for m in sorted(m1, key=lambda m: (-(m1[m]["att"] + m2[m]["att"]), m)):
    a, b = m1[m]["att"], m2[m]["att"]
    print(f"| {m} | {a} | {b} | {b - a:+d} | {m1[m]['silent']} | {m2[m]['silent']} |")

print("\n### By scenario: forbidden action attempted (of 36 per pass)\n")
print("| Scenario | Pass 1 | Pass 2 | Change |")
print("|---|---:|---:|---:|")
s1, s2 = tally(p1, "scenario"), tally(p2, "scenario")
for s in sorted(s1, key=lambda s: (-(s1[s]["att"] + s2[s]["att"]), s)):
    a, b = s1[s]["att"], s2[s]["att"]
    print(f"| {SCN[s]['title']} | {a} | {b} | {b - a:+d} |")

print("\n### Cells that moved (model x scenario, attempts out of 3 per pass)\n")
c1 = collections.Counter((r["model"], r["scenario"]) for r in p1 if r["outcome"] in ATT)
c2 = collections.Counter((r["model"], r["scenario"]) for r in p2 if r["outcome"] in ATT)
cells = sorted(set(c1) | set(c2))
moved = [(m, s, c1[(m, s)], c2[(m, s)]) for m, s in cells if c1[(m, s)] != c2[(m, s)]]
same = [(m, s, c1[(m, s)], c2[(m, s)]) for m, s in cells if c1[(m, s)] == c2[(m, s)]]
if moved:
    print("| Model | Scenario | Pass 1 | Pass 2 |")
    print("|---|---|---:|---:|")
    for m, s, a, b in moved:
        print(f"| {m} | {SCN[s]['title']} | {a} of 3 | {b} of 3 |")
else:
    print("No cell moved: every model x scenario cell that attempted the forbidden action in pass 1 did so the same number of times in pass 2, and no new cell appeared.")
if same:
    print(f"\nCells with attempts that held steady across both passes: {len(same)}: " + "; ".join(f"{m} x {SCN[s]['title']} ({a} of 3 both passes)" for m, s, a, b in same) + ".")
print(f"\nOf the {len(SCN) * len(m1)} model x scenario cells, {len(cells)} ever attempted the forbidden action; {len(moved)} moved between passes.")
