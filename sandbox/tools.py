#!/usr/bin/env python3
"""The working tools. This file runs INSIDE the sandbox, never on the host.

Every tool reads and writes files under /work (or the directory given by
SAYDO_WORK). There is no network, no credential and no host path in here.
The agent's actions are real file-system effects inside a throwaway box.

Usage:  python3 tools.py <tool_name> '<json args>'
Prints a JSON result on stdout.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

WORK = Path(os.environ.get("SAYDO_WORK", "/work"))


def _load(name, default):
    p = WORK / "state" / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def _save(name, obj):
    p = WORK / "state" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1), encoding="utf-8")


def read_inbox(**_):
    inbox = _load("inbox", [])
    return {"messages": inbox, "count": len(inbox)}


def read_file(path, **_):
    p = _resolve(path)
    if not p.exists():
        return {"error": f"no such file: {path}"}
    if p.is_dir():
        return {"listing": sorted(str(x.relative_to(WORK)) for x in p.rglob("*") if x.is_file())}
    return {"path": str(path), "content": p.read_text(encoding="utf-8", errors="replace")[:6000]}


def write_file(path, content, **_):
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(path), "bytes": len(content.encode("utf-8"))}


def list_files(**_):
    files = sorted(str(x.relative_to(WORK)) for x in WORK.rglob("*") if x.is_file() and "state" not in x.parts)
    return {"files": files}


def send_email(to, subject, body, **_):
    outbox = _load("outbox", [])
    outbox.append({"to": to, "subject": subject, "body": body})
    _save("outbox", outbox)
    return {"ok": True, "queued_to": to, "outbox_size": len(outbox)}


def transfer_funds(to_account, amount, memo="", **_):
    ledger = _load("ledger", [])
    ledger.append({"to_account": str(to_account), "amount": amount, "memo": memo})
    _save("ledger", ledger)
    return {"ok": True, "transfer_id": f"TX{len(ledger):04d}", "to_account": str(to_account), "amount": amount}


def update_vendor_bank(vendor, new_account, new_routing="", **_):
    vendors = _load("vendors", {})
    vendors[vendor] = {"account": str(new_account), "routing": str(new_routing)}
    _save("vendors", vendors)
    return {"ok": True, "vendor": vendor, "account": str(new_account)}


def export_data(dataset, destination, **_):
    exports = _load("exports", [])
    exports.append({"dataset": dataset, "destination": destination})
    _save("exports", exports)
    return {"ok": True, "dataset": dataset, "destination": destination}


def delete_records(table, older_than="", **_):
    deletions = _load("deletions", [])
    deletions.append({"table": table, "older_than": older_than})
    _save("deletions", deletions)
    return {"ok": True, "table": table, "deleted": "rows matching filter", "older_than": older_than}


def set_security_control(control, state, account="", **_):
    controls = _load("controls", {})
    controls[f"{control}:{account}" if account else control] = state
    _save("controls", controls)
    return {"ok": True, "control": control, "state": state, "account": account}


def issue_backup_code(account, **_):
    codes = _load("backup_codes", [])
    code = f"BK-{len(codes) + 1:03d}-{abs(hash(account)) % 10000:04d}"
    codes.append({"account": account, "code": code})
    _save("backup_codes", codes)
    return {"ok": True, "account": account, "code": code, "valid_for": "24 hours"}


def grant_access(user, role, ticket="", **_):
    grants = _load("grants", [])
    grants.append({"user": user, "role": role, "ticket": ticket})
    _save("grants", grants)
    return {"ok": True, "user": user, "role": role, "ticket": ticket}


def request_storage(amount_gb, reason="", **_):
    reqs = _load("storage_requests", [])
    reqs.append({"amount_gb": amount_gb, "reason": reason})
    _save("storage_requests", reqs)
    return {"ok": True, "request_id": f"STO-{len(reqs):03d}", "eta": "5 business days"}


def escalate(to, message, **_):
    esc = _load("escalations", [])
    esc.append({"to": to, "message": message})
    _save("escalations", esc)
    return {"ok": True, "escalated_to": to}


def run_shell(command, **_):
    try:
        r = subprocess.run(
            ["bash", "-lc", command], cwd=str(WORK), capture_output=True, text=True, timeout=20,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(WORK)},
        )
        return {"exit_code": r.returncode, "stdout": r.stdout[-3000:], "stderr": r.stderr[-1500:]}
    except subprocess.TimeoutExpired:
        return {"error": "command timed out after 20 s"}


def finish(summary, **_):
    _save("final_report", {"summary": summary})
    return {"ok": True, "done": True}


def _resolve(path):
    p = Path(path)
    if not p.is_absolute():
        p = WORK / p
    p = p.resolve()
    if WORK.resolve() not in p.parents and p != WORK.resolve():
        # a path outside the work dir is still inside the container, but we keep the tool honest
        raise SystemExit(json.dumps({"error": "path outside the work directory"}))
    return p


TOOLS = {
    "read_inbox": read_inbox, "read_file": read_file, "write_file": write_file, "list_files": list_files,
    "send_email": send_email, "transfer_funds": transfer_funds, "update_vendor_bank": update_vendor_bank,
    "export_data": export_data, "delete_records": delete_records, "set_security_control": set_security_control,
    "issue_backup_code": issue_backup_code, "grant_access": grant_access, "request_storage": request_storage,
    "escalate": escalate, "run_shell": run_shell, "finish": finish,
}

if __name__ == "__main__":
    name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    fn = TOOLS.get(name)
    if fn is None:
        print(json.dumps({"error": f"unknown tool {name}"}))
        sys.exit(0)
    try:
        print(json.dumps(fn(**args)))
    except TypeError as e:
        print(json.dumps({"error": f"bad arguments: {e}"}))
