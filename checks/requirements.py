"""Load and validate a requirements file (format: requirements/README.md)."""
from pathlib import Path

import yaml

AREAS = {"licenses-users", "permissions", "objects-config", "automations", "limits"}
SEVERITIES = {"high", "medium", "low"}


class RequirementsError(Exception):
    pass


def load(path, require_approved=True):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "rules" not in data:
        raise RequirementsError(f"{path}: not a requirements file (no 'rules')")
    if require_approved and data.get("status") != "approved":
        # Guardrail 3: nothing runs until the consultant approves.
        raise RequirementsError(
            f"{path}: status is '{data.get('status')}'. Checks run only on approved requirements "
            "(guardrail 3). The consultant sets status: approved, approved_by and approved_on."
        )
    if require_approved and not (data.get("approved_by") and data.get("approved_on")):
        raise RequirementsError(f"{path}: approved, but approved_by or approved_on is empty.")
    seen = set()
    for rule in data["rules"]:
        for check in rule.get("checks") or []:
            cid = check.get("id")
            if not cid or cid in seen:
                raise RequirementsError(f"{path}: missing or repeated check id: {cid}")
            seen.add(cid)
            if check.get("area") not in AREAS:
                raise RequirementsError(f"{path}: {cid}: unknown area '{check.get('area')}'")
            if check.get("severity") not in SEVERITIES:
                raise RequirementsError(f"{path}: {cid}: severity must be one of {sorted(SEVERITIES)}")
            if check.get("how") == "code" and not isinstance(check.get("rule"), dict):
                raise RequirementsError(f"{path}: {cid}: a 'how: code' check needs a 'rule'")
    return data
