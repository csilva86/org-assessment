"""Run every check of an approved requirements file against a snapshot."""
import datetime as _dt

from .requirements import load as load_requirements
from .rules import RULES
from .snapshot import Snapshot, SnapshotError

STATUSES = ("met", "partial", "not_met", "needs_judgement", "error")


def run(requirements_path, snapshot_folder):
    req = load_requirements(requirements_path)
    snap = Snapshot(snapshot_folder)
    results = []
    for rule in req["rules"]:
        for check in rule.get("checks") or []:
            base = {
                "check_id": check["id"],
                "business_rule_id": rule["id"],          # traceability back to the client's words
                "business_rule": rule.get("business_rule"),
                "area": check["area"],
                "what": check.get("what"),
                "severity": check["severity"],
                "how": check.get("how"),
            }
            if check.get("how") != "code":
                results.append({**base, "status": "needs_judgement",
                                "summary": "Judgement check: reviewed by the consultant, not by code.",
                                "evidence": []})
                continue
            params = dict(check["rule"])
            rtype = params.pop("type", None)
            fn = RULES.get(rtype)
            if fn is None:
                results.append({**base, "status": "error",
                                "summary": f"Unknown rule type '{rtype}'.", "evidence": []})
                continue
            try:
                outcome = fn(snap, **params)
            except SnapshotError as e:
                outcome = {"status": "error", "summary": f"Cannot evaluate: {e}.", "evidence": []}
            except (TypeError, ValueError) as e:
                outcome = {"status": "error", "summary": f"Bad rule parameters: {e}.", "evidence": []}
            results.append({**base, "rule": check["rule"], **outcome})

    counts = {s: sum(1 for r in results if r["status"] == s) for s in STATUSES}
    return {
        "requirements": str(requirements_path),
        "project": req.get("project"),
        "approved_by": req.get("approved_by"),
        "approved_on": str(req.get("approved_on")),
        "snapshot": str(snapshot_folder),
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "counts": counts,
        "results": results,
    }
