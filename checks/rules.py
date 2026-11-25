"""
Deterministic rule types (guardrail 4: code before AI).

Every rule reads only the snapshot and returns:
    {"status": "met" | "partial" | "not_met",
     "summary": "<one sentence>",
     "evidence": [{"file": "<area>/<name>.json", "where": {...}, "values": {...}}]}
(guardrail 5: every conclusion carries the data that proves it).

To add a rule type: write a function `rule_<type>(snapshot, **params)`, register it in RULES,
document it in requirements/README.md and test it in tests/test_checks.py.
"""


def _verdict(ok_count, total):
    if total and ok_count == total:
        return "met"
    if ok_count:
        return "partial"
    return "not_met"


def _ev(file, where=None, values=None):
    item = {"file": file}
    if where:
        item["where"] = where
    if values is not None:
        item["values"] = values
    return item


# ---------------------------------------------------------------- objects-config
def rule_objects_exist(snap, objects):
    """Every object in `objects` exists in the org (API names, e.g. Case, Library_Book__c)."""
    available = set(snap.load("objects-config", "sobjects"))
    found = [o for o in objects if o in available]
    missing = [o for o in objects if o not in available]
    summary = f"{len(found)} of {len(objects)} objects exist."
    if missing:
        summary += " Missing: " + ", ".join(missing) + "."
    return {
        "status": _verdict(len(found), len(objects)),
        "summary": summary,
        "evidence": [_ev(snap.ref("objects-config", "sobjects"), values={"found": found, "missing": missing})],
    }


PICKLIST_MATCH = ("exact", "includes")
PICKLIST_COMPARE = ("value", "label")


def rule_picklist_values(snap, object, field, values, match="exact", compare="value", ordered=False):
    """The active values of picklist `field` on `object` (from describe-<object>.json) are `values`.
    match: exact (no other active values) or includes (others allowed). compare: the API value or
    the label. ordered: the expected values appear in this order among the active ones."""
    if match not in PICKLIST_MATCH:
        raise ValueError(f"unknown match '{match}'; use {list(PICKLIST_MATCH)}")
    if compare not in PICKLIST_COMPARE:
        raise ValueError(f"unknown compare '{compare}'; use {list(PICKLIST_COMPARE)}")
    name = f"describe-{object}"
    describe = snap.load("objects-config", name)
    fld = next((f for f in describe.get("fields", []) if f.get("name") == field), None)
    if fld is None:
        return {"status": "not_met", "summary": f"Field {object}.{field} not found.",
                "evidence": [_ev(snap.ref("objects-config", name), {"field": field}, {"found": False})]}
    active = [pv.get(compare) for pv in fld.get("picklistValues") or [] if pv.get("active")]
    found = [v for v in values if v in active]
    missing = [v for v in values if v not in active]
    extra = [a for a in active if a not in values]
    order_ok = [a for a in active if a in values] == found
    problems = []
    if missing:
        problems.append("missing: " + ", ".join(missing))
    if match == "exact" and extra:
        problems.append("other active values: " + ", ".join(extra))
    if ordered and not order_ok:
        problems.append("order differs: " + ", ".join(a for a in active if a in values))
    if not found:
        status = "not_met"
    elif problems:
        status = "partial"
    else:
        status = "met"
    summary = f"{len(found)} of {len(values)} expected values are active on {object}.{field}."
    if problems:
        summary += " " + "; ".join(problems) + "."
    return {"status": status, "summary": summary,
            "evidence": [_ev(snap.ref("objects-config", name),
                             {"field": field, "picklistValues": {"active": True}, "compare": compare},
                             {"active": active, "missing": missing, "extra": extra, "order_ok": order_ok})]}


# ---------------------------------------------------------------- licenses-users
def rule_licenses_available(snap, licenses, min_available):
    """Unused licenses (total minus used), summed over the named user licenses or permission
    set licenses, are at least `min_available`."""
    evidence, free, matched = [], 0, []
    sources = [
        ("user-licenses", ("Name",)),
        ("permission-set-licenses", ("MasterLabel", "DeveloperName")),
    ]
    for name, keys in sources:
        for rec in snap.records("licenses-users", name):
            label = next((rec[k] for k in keys if rec.get(k) in licenses), None)
            if label is None:
                continue
            available = (rec.get("TotalLicenses") or 0) - (rec.get("UsedLicenses") or 0)
            free += available
            matched.append(label)
            evidence.append(_ev(snap.ref("licenses-users", name), {keys[0]: rec.get(keys[0])},
                                {"TotalLicenses": rec.get("TotalLicenses"),
                                 "UsedLicenses": rec.get("UsedLicenses"), "available": available}))
    unknown = [l for l in licenses if l not in matched]
    if free >= min_available:
        status = "met"
    elif free > 0:
        status = "partial"
    else:
        status = "not_met"
    summary = f"{free} licenses available, {min_available} needed."
    if unknown:
        summary += " Not found in the org: " + ", ".join(unknown) + "."
    return {"status": status, "summary": summary, "evidence": evidence}


# ---------------------------------------------------------------- permissions
ACCESS_FIELDS = {
    "read": "PermissionsRead", "create": "PermissionsCreate", "edit": "PermissionsEdit",
    "delete": "PermissionsDelete", "view_all": "PermissionsViewAllRecords",
    "modify_all": "PermissionsModifyAllRecords",
}


def _find_permission_sets(snap, names):
    """Match permission sets by API name, label, or (for profiles) the profile name."""
    found = {}
    for rec in snap.records("permissions", "permission-sets"):
        profile = (rec.get("Profile") or {}).get("Name") if rec.get("IsOwnedByProfile") else None
        for n in names:
            if n in (rec.get("Name"), rec.get("Label"), profile):
                found[n] = rec
    return found


def rule_object_access(snap, permission_sets, object, access):
    """Each named permission set (or profile) grants `access` (read/create/edit/delete/
    view_all/modify_all) on `object`."""
    unknown = [a for a in access if a not in ACCESS_FIELDS]
    if unknown:
        raise ValueError(f"unknown access: {unknown}; use {sorted(ACCESS_FIELDS)}")
    sets = _find_permission_sets(snap, permission_sets)
    perms = {}
    for rec in snap.records("permissions", "object-permissions"):
        if rec.get("SobjectType") == object:
            perms[rec.get("ParentId")] = rec
    ok, evidence, lacking = 0, [], []
    for n in permission_sets:
        ps = sets.get(n)
        if ps is None:
            lacking.append(f"{n} (not found)")
            evidence.append(_ev(snap.ref("permissions", "permission-sets"), {"name": n}, {"found": False}))
            continue
        row = perms.get(ps["Id"], {})
        values = {a: bool(row.get(ACCESS_FIELDS[a])) for a in access}
        missing = [a for a, v in values.items() if not v]
        evidence.append(_ev(snap.ref("permissions", "object-permissions"),
                            {"ParentId": ps["Id"], "SobjectType": object, "permission_set": n}, values))
        if missing:
            lacking.append(f"{n} lacks {', '.join(missing)}")
        else:
            ok += 1
    summary = f"{ok} of {len(permission_sets)} grant {', '.join(access)} on {object}."
    if lacking:
        summary += " " + "; ".join(lacking) + "."
    return {"status": _verdict(ok, len(permission_sets)), "summary": summary, "evidence": evidence}


def rule_system_permissions_absent(snap, permission_sets, permissions):
    """None of the named permission sets (or profiles) has any of the given system permissions
    (field names such as PermissionsModifyAllData)."""
    sets = _find_permission_sets(snap, permission_sets)
    clean, evidence, offenders = 0, [], []
    for n in permission_sets:
        ps = sets.get(n)
        if ps is None:
            offenders.append(f"{n} (not found)")
            evidence.append(_ev(snap.ref("permissions", "permission-sets"), {"name": n}, {"found": False}))
            continue
        has = [p for p in permissions if ps.get(p)]
        evidence.append(_ev(snap.ref("permissions", "permission-sets"), {"Id": ps["Id"], "name": n},
                            {p: bool(ps.get(p)) for p in permissions}))
        if has:
            offenders.append(f"{n} has {', '.join(has)}")
        else:
            clean += 1
    summary = f"{clean} of {len(permission_sets)} are free of {', '.join(permissions)}."
    if offenders:
        summary += " " + "; ".join(offenders) + "."
    return {"status": _verdict(clean, len(permission_sets)), "summary": summary, "evidence": evidence}


# ---------------------------------------------------------------- automations
def rule_no_legacy_automation(snap, object, object_label=None):
    """No workflow rule and no active Process Builder process runs on `object`.
    Process Builder is matched by the object's label, as FlowDefinitionView reports it."""
    label = object_label or object
    wf = [r for r in snap.records("automations", "workflow-rules") if r.get("TableEnumOrId") == object]
    pb = [r for r in snap.records("automations", "flows")
          if r.get("ProcessType") == "Workflow" and r.get("IsActive")
          and r.get("TriggerObjectOrEventLabel") == label]
    evidence = [_ev(snap.ref("automations", "workflow-rules"), {"TableEnumOrId": object},
                    {"names": [r.get("Name") for r in wf]}),
                _ev(snap.ref("automations", "flows"),
                    {"ProcessType": "Workflow", "IsActive": True, "TriggerObjectOrEventLabel": label},
                    {"names": [r.get("ApiName") for r in pb]})]
    count = len(wf) + len(pb)
    summary = (f"No legacy automation on {object}." if count == 0 else
               f"{len(wf)} workflow rule(s) and {len(pb)} active Process Builder process(es) on {object}.")
    return {"status": "met" if count == 0 else "not_met", "summary": summary, "evidence": evidence}


# ---------------------------------------------------------------- limits
def rule_limit_usage_below(snap, limit, max_percent):
    """The org limit `limit` (e.g. DailyApiRequests) is used below `max_percent` percent."""
    rows = [r for r in snap.load("limits", "limits") if r.get("name") == limit]
    if not rows:
        return {"status": "not_met", "summary": f"Limit {limit} not found in the snapshot.",
                "evidence": [_ev(snap.ref("limits", "limits"), {"name": limit}, {"found": False})]}
    row = rows[0]
    maximum, remaining = row.get("max") or 0, row.get("remaining") or 0
    used_pct = round(100 * (maximum - remaining) / maximum, 1) if maximum else 0.0
    status = "met" if used_pct < max_percent else "not_met"
    return {"status": status,
            "summary": f"{limit}: {used_pct}% used, threshold {max_percent}%.",
            "evidence": [_ev(snap.ref("limits", "limits"), {"name": limit},
                             {"max": maximum, "remaining": remaining, "used_percent": used_pct})]}


RULES = {
    "objects_exist": rule_objects_exist,
    "picklist_values": rule_picklist_values,
    "licenses_available": rule_licenses_available,
    "object_access": rule_object_access,
    "system_permissions_absent": rule_system_permissions_absent,
    "no_legacy_automation": rule_no_legacy_automation,
    "limit_usage_below": rule_limit_usage_below,
}
