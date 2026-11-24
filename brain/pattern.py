"""Load and validate a second-brain pattern file (format: brain/README.md)."""
import re
from pathlib import Path

import yaml

from checks.requirements import AREAS, SEVERITIES
from checks.rules import RULES

KINDS = {"rule-to-checks", "recurring-gap", "lesson"}
STATUSES = {"proposed", "approved"}
HOWS = {"code", "judgement"}
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PLACEHOLDER = re.compile(r"^<[a-z][a-z0-9_]*>$")

# Fields each kind must fill in, besides the common ones.
REQUIRED = {
    "rule-to-checks": ("applies_when", "checks"),
    "recurring-gap": ("applies_when", "symptom", "usual_cause", "fix"),
    "lesson": ("lesson",),
}


class PatternError(Exception):
    pass


def load(path):
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise PatternError(f"{path}: cannot read: {e}")
    validate(data, path)
    return data


def validate(data, path):
    if not isinstance(data, dict):
        raise PatternError(f"{path}: not a pattern file")
    pid = data.get("id")
    if not isinstance(pid, str) or not ID.match(pid):
        raise PatternError(f"{path}: id must be lowercase words joined by '-' (e.g. sla-needs-entitlements)")
    if Path(path).stem != pid:
        raise PatternError(f"{path}: the file name must be the id: {pid}.yaml")
    kind = data.get("kind")
    if kind not in KINDS:
        raise PatternError(f"{path}: kind must be one of {sorted(KINDS)}")
    if not data.get("title"):
        raise PatternError(f"{path}: title is empty")
    status = data.get("status")
    if status not in STATUSES:
        raise PatternError(f"{path}: status must be one of {sorted(STATUSES)}")
    if status == "approved" and not (data.get("approved_by") and data.get("approved_on")):
        raise PatternError(f"{path}: approved, but approved_by or approved_on is empty")
    if status == "proposed" and (data.get("approved_by") or data.get("approved_on")):
        raise PatternError(f"{path}: a proposal cannot carry an approval. Only `python -m brain approve` sets it.")
    for field in REQUIRED[kind]:
        if not data.get(field):
            raise PatternError(f"{path}: a {kind} pattern needs '{field}'")
    seen = data.get("seen_in_projects", 1)
    if not isinstance(seen, int) or isinstance(seen, bool) or seen < 1:
        raise PatternError(f"{path}: seen_in_projects must be a whole number, 1 or more")
    tags = data.get("tags") or []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise PatternError(f"{path}: tags must be a list of words")
    for i, check in enumerate(data.get("checks") or [], 1):
        _validate_check(check, f"{path}: check {i}")


def _validate_check(check, where):
    if not isinstance(check, dict):
        raise PatternError(f"{where}: not a check")
    if "id" in check:
        raise PatternError(f"{where}: no 'id' in a pattern. Ids belong to the project's requirements file.")
    if check.get("area") not in AREAS:
        raise PatternError(f"{where}: area must be one of {sorted(AREAS)}")
    if check.get("severity") not in SEVERITIES:
        raise PatternError(f"{where}: severity must be one of {sorted(SEVERITIES)}")
    if check.get("how") not in HOWS:
        raise PatternError(f"{where}: how must be 'code' or 'judgement'")
    if not check.get("what"):
        raise PatternError(f"{where}: 'what' is empty")
    if check["how"] == "code":
        rule = check.get("rule")
        if not isinstance(rule, dict) or rule.get("type") not in RULES:
            raise PatternError(f"{where}: a 'how: code' check needs a rule whose type is one of {sorted(RULES)}")
        for key, value in rule.items():
            for v in value if isinstance(value, list) else [value]:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    # Thresholds come from the client's requirement, not from the pattern.
                    raise PatternError(
                        f"{where}: rule.{key} is the number {v}. Numbers in a check come from the client: "
                        f"write a placeholder such as <{key}>."
                    )


def is_placeholder(value):
    return isinstance(value, str) and bool(PLACEHOLDER.match(value))
