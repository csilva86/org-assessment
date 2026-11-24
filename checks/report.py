"""
Reports built from results.json by code, never written by AI (guardrails 4 and 5):

- client-summary.md    one line per business rule, in the client's words, no technical ids
- consultant-detail.md every check with its evidence and a recommended fix
- gaps.json            what is not met, for the future development pipeline

Same results.json in, same reports out.
"""
import json
from pathlib import Path

AREA_NAMES = {
    "licenses-users": "Licenses and users",
    "permissions": "Permissions",
    "objects-config": "Objects and configuration",
    "automations": "Automations",
    "limits": "Limits",
}
STATUS_LABEL = {
    "met": "Met",
    "partial": "Partly met",
    "not_met": "Not met",
    "needs_judgement": "Awaiting consultant review",
    "error": "Could not be assessed",
}
STATUS_MARK = {"met": "✅", "partial": "🟡", "not_met": "❌", "needs_judgement": "👀", "error": "⚠️"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
GAP_STATUSES = ("not_met", "partial")


# ---------------------------------------------------------------- recommendations
def _list(items):
    items = [str(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def recommend(result):
    """A recommended fix, from a template per rule type. None when nothing needs fixing."""
    status = result["status"]
    if status == "met":
        return None
    if status == "needs_judgement":
        return "Review the evidence and record the decision in the requirements file."
    if status == "error":
        return "Collect the snapshot again (see the collector's manifest) and re-run the checks."
    rule = result.get("rule") or {}
    t = rule.get("type")
    if t == "objects_exist":
        missing = (result.get("evidence") or [{}])[0].get("values", {}).get("missing") or rule.get("objects", [])
        return (f"Make {_list(missing)} available: enable the Salesforce feature that provides it, "
                "or deploy the custom object.")
    if t == "licenses_available":
        return (f"Free up or buy licenses of type {_list(rule.get('licenses', []))} until at least "
                f"{rule.get('min_available')} are available. Frozen users still hold a license; deactivated users do not.")
    if t == "object_access":
        return (f"Grant {_list(rule.get('access', []))} on {rule.get('object')} through a permission set "
                f"({_list(rule.get('permission_sets', []))}) assigned to the users who need it, "
                "rather than through profiles.")
    if t == "system_permissions_absent":
        return (f"Remove {_list(rule.get('permissions', []))} from {_list(rule.get('permission_sets', []))}. "
                "Keep admin-level permissions in a separate permission set for administrators only.")
    if t == "no_legacy_automation":
        return (f"Migrate the workflow rules and Process Builder processes on {rule.get('object')} to Flow "
                "(Salesforce's Migrate to Flow tool covers most cases), then deactivate them.")
    if t == "limit_usage_below":
        return (f"Reduce usage of {rule.get('limit')} below {rule.get('max_percent')}%: review integrations "
                "and jobs that consume it, or raise the limit with Salesforce.")
    return "Review this check with the consultant."


# ---------------------------------------------------------------- rule-level verdicts
def rule_status(statuses):
    """One verdict for a business rule from its checks' statuses."""
    s = set(statuses)
    if "not_met" in s:
        return "not_met"
    if "partial" in s:
        return "partial"
    if "error" in s:
        return "error"
    if s == {"needs_judgement"}:
        return "needs_judgement"
    return "met"


def group_by_rule(results):
    rules = {}
    for r in results:
        g = rules.setdefault(r["business_rule_id"], {"id": r["business_rule_id"],
                                                     "text": r.get("business_rule"), "checks": []})
        g["checks"].append(r)
    for g in rules.values():
        g["status"] = rule_status([c["status"] for c in g["checks"]])
        g["pending_review"] = any(c["status"] == "needs_judgement" for c in g["checks"]) and g["status"] != "needs_judgement"
        g["severity"] = min((c["severity"] for c in g["checks"]), key=lambda s: SEVERITY_ORDER[s])
    return list(rules.values())


# ---------------------------------------------------------------- client summary
def client_summary(report):
    rules = group_by_rule(report["results"])
    counts = {k: sum(1 for g in rules if g["status"] == k) for k in STATUS_LABEL}
    lines = [
        f"# Org assessment — {report.get('project')}",
        "",
        f"Requirements approved by {report.get('approved_by')} on {report.get('approved_on')}. "
        f"Org data as collected in snapshot `{Path(report['snapshot']).name}`.",
        "",
        f"**{counts['met']} of {len(rules)} business rules are met.** "
        + ", ".join(f"{counts[k]} {STATUS_LABEL[k].lower()}" for k in ("partial", "not_met", "error", "needs_judgement")
                    if counts[k]) + ("." if any(counts[k] for k in ("partial", "not_met", "error", "needs_judgement")) else ""),
        "",
        "## Business rules",
        "",
        "| | Business rule | Verdict |",
        "| --- | --- | --- |",
    ]
    for g in rules:
        verdict = STATUS_LABEL[g["status"]]
        if g["pending_review"]:
            verdict += " (one point awaits consultant review)"
        lines.append(f"| {STATUS_MARK[g['status']]} | {g['text']} | {verdict} |")

    lines += ["", "## By area", "", "| Area | Checks met | Of |", "| --- | --- | --- |"]
    for area, name in AREA_NAMES.items():
        checks = [r for r in report["results"] if r["area"] == area and r["status"] != "needs_judgement"]
        if checks:
            met = sum(1 for r in checks if r["status"] == "met")
            lines.append(f"| {name} | {met} | {len(checks)} |")

    gaps = sorted((r for r in report["results"] if r["status"] in GAP_STATUSES),
                  key=lambda r: (SEVERITY_ORDER[r["severity"]], r["check_id"]))
    lines += ["", "## What needs attention", ""]
    if gaps:
        for r in gaps:
            lines.append(f"- **{r['what'].rstrip('.')}** — {STATUS_LABEL[r['status']].lower()}, {r['severity']} priority.")
    else:
        lines.append("Nothing: every check that can be verified by code is met.")
    errors = [r for r in report["results"] if r["status"] == "error"]
    if errors:
        lines += ["", f"{len(errors)} check(s) could not be assessed because data was missing; "
                      "they are listed in the consultant report."]
    lines += ["", "---", "", "Every verdict above is backed by data from the org; the consultant report lists it."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- consultant detail
def _evidence_lines(evidence):
    out = []
    for ev in evidence or []:
        where = ", ".join(f"{k}={v}" for k, v in (ev.get("where") or {}).items())
        values = json.dumps(ev.get("values"), ensure_ascii=False) if "values" in ev else ""
        out.append(f"  - `{ev['file']}`" + (f" where {where}" if where else "") + (f": {values}" if values else ""))
    return out


def consultant_detail(report):
    c = report["counts"]
    lines = [
        f"# Consultant report — {report.get('project')}",
        "",
        "| | |",
        "| --- | --- |",
        f"| Requirements | `{report['requirements']}` (approved by {report.get('approved_by')} on {report.get('approved_on')}) |",
        f"| Snapshot | `{report['snapshot']}` |",
        f"| Generated | {report['generated_at']} |",
        f"| Results | {c['met']} met · {c['partial']} partial · {c['not_met']} not met · "
        f"{c['needs_judgement']} need judgement · {c['error']} error(s) |",
        "",
    ]
    for g in group_by_rule(report["results"]):
        lines += [f"## {g['id']} — {g['text']}", "", f"Verdict: {STATUS_MARK[g['status']]} **{STATUS_LABEL[g['status']]}**", ""]
        for r in g["checks"]:
            lines += [
                f"### {STATUS_MARK[r['status']]} {r['check_id']} · {r['what']}",
                "",
                f"- Status: **{STATUS_LABEL[r['status']]}** · severity {r['severity']} · area {AREA_NAMES.get(r['area'], r['area'])} · {r['how']}",
                f"- Result: {r['summary']}",
            ]
            if r.get("rule"):
                lines.append(f"- Rule: `{json.dumps(r['rule'], ensure_ascii=False)}`")
            ev = _evidence_lines(r.get("evidence"))
            if ev:
                lines += ["- Evidence:"] + ev
            fix = recommend(r)
            if fix:
                lines.append(f"- Recommended: {fix}")
            lines.append("")
    lines += ["## Method", "",
              "Org data was collected read-only into the snapshot above. Every `code` check is deterministic Python "
              "(`checks/rules.py`) run on that snapshot; `judgement` checks are left to the consultant. "
              "Recommendations come from fixed templates per rule type (`checks/report.py`)."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- gaps
def gaps(report):
    items = []
    for r in report["results"]:
        if r["status"] not in GAP_STATUSES:
            continue
        items.append({
            "check_id": r["check_id"],
            "business_rule_id": r["business_rule_id"],
            "business_rule": r.get("business_rule"),
            "area": r["area"],
            "severity": r["severity"],
            "status": r["status"],
            "what": r.get("what"),
            "rule": r.get("rule"),
            "summary": r["summary"],
            "recommendation": recommend(r),
            "evidence": r.get("evidence", []),
        })
    items.sort(key=lambda g: (SEVERITY_ORDER[g["severity"]], g["check_id"]))
    return {
        "project": report.get("project"),
        "snapshot": report["snapshot"],
        "requirements": report["requirements"],
        "generated_at": report["generated_at"],
        "not_assessed": [r["check_id"] for r in report["results"] if r["status"] == "error"],
        "gaps": items,
    }


def write_all(report, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = {
        "client-summary.md": client_summary(report),
        "consultant-detail.md": consultant_detail(report),
        "gaps.json": json.dumps(gaps(report), indent=2, ensure_ascii=False) + "\n",
    }
    for name, text in written.items():
        (folder / name).write_text(text, encoding="utf-8")
    return [folder / n for n in written]
