"""
Org documentation built by code from a snapshot (no AI, no live org).

The document is a list of sections; each section has an intro and tables. The same structure is
rendered to Markdown and to self-contained HTML, so both always say the same thing.
Users appear only as counts by profile and license: never by name.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from checks.snapshot import Snapshot, SnapshotError

ACCESS = [("R", "PermissionsRead"), ("C", "PermissionsCreate"), ("E", "PermissionsEdit"),
          ("D", "PermissionsDelete"), ("V", "PermissionsViewAllRecords"), ("M", "PermissionsModifyAllRecords")]
ADMIN_PERMISSIONS = [("Modify All Data", "PermissionsModifyAllData"), ("View All Data", "PermissionsViewAllData"),
                     ("Customize Application", "PermissionsCustomizeApplication"),
                     ("Manage Users", "PermissionsManageUsers"), ("Author Apex", "PermissionsAuthorApex")]
OLD_API_VERSION = 50       # Apex classes below this version are flagged for review


class Section:
    def __init__(self, id, title, intro="", tables=None, notes=None):
        self.id, self.title, self.intro = id, title, intro
        self.tables = tables or []          # [(caption, headers, rows)]
        self.notes = notes or []
        self.sources = []                   # [(area, name)] used, for the methodology appendix


def _try(fn, default=None):
    try:
        return fn()
    except SnapshotError:
        return default


def _records(snap, area, name, section):
    section.sources.append((area, name))
    return _try(lambda: snap.records(area, name), [])


def _ps_name(rec):
    if rec.get("IsOwnedByProfile"):
        return "Profile: " + ((rec.get("Profile") or {}).get("Name") or rec.get("Name"))
    return rec.get("Label") or rec.get("Name")


# ---------------------------------------------------------------- sections
def overview(snap):
    s = Section("overview", "Overview")
    s.sources.append(("objects-config", "organization"))
    org = (_try(lambda: snap.records("objects-config", "organization"), []) or [{}])[0]
    times = []
    for area in ("licenses-users", "permissions", "objects-config", "automations", "limits"):
        m = snap.manifest(area) or {}
        times += [f["ran_at"] for f in m.get("files", []) if f.get("ran_at")]
    s.intro = "What the org is and when this documentation's data was collected."
    s.tables.append((None, ["Item", "Value"], [
        ["Org Id", org.get("Id", "—")],
        ["Edition", org.get("OrganizationType", "—")],
        ["Instance", org.get("InstanceName", "—")],
        ["Environment", "—" if "IsSandbox" not in org else ("Sandbox" if org["IsSandbox"] else "Production-type org")],
        ["Language", org.get("LanguageLocaleKey", "—")],
        ["Data collected (UTC)", f"{min(times)} to {max(times)}" if times else "—"],
    ]))
    return s


def licenses_users(snap):
    s = Section("licenses", "Licenses and users",
                "Licenses in use and available. Users are counted by profile and license, never listed by name.")
    lic = [r for r in _records(snap, "licenses-users", "user-licenses", s) if (r.get("TotalLicenses") or 0) > 0]
    lic.sort(key=lambda r: -(r.get("UsedLicenses") or 0))
    s.tables.append(("User licenses", ["License", "Total", "Used", "Available"],
                     [[r["Name"], r["TotalLicenses"], r["UsedLicenses"], r["TotalLicenses"] - r["UsedLicenses"]] for r in lic]))
    psl = [r for r in _records(snap, "licenses-users", "permission-set-licenses", s) if (r.get("UsedLicenses") or 0) > 0]
    psl.sort(key=lambda r: -(r.get("UsedLicenses") or 0))
    if psl:
        s.tables.append(("Permission set licenses in use", ["License", "Total", "Used"],
                         [[r.get("MasterLabel"), r.get("TotalLicenses"), r.get("UsedLicenses")] for r in psl]))
    pkg = _records(snap, "licenses-users", "package-licenses", s)
    if pkg:
        s.tables.append(("Package licenses", ["Namespace", "Status", "Allowed", "Used"],
                         [[r.get("NamespacePrefix"), r.get("Status"), r.get("AllowedLicenses"), r.get("UsedLicenses")] for r in pkg]))
    users = _records(snap, "licenses-users", "users", s)
    by = Counter()
    for u in users:
        if u.get("IsActive"):
            prof = (u.get("Profile") or {})
            by[(prof.get("Name") or "(no profile: platform or automated user)",
                (prof.get("UserLicense") or {}).get("Name") or "—")] += 1
    active = sum(by.values())
    s.notes.append(f"{active} active and {len(users) - active} inactive users.")
    s.tables.append(("Active users by profile", ["Profile", "License", "Users"],
                     [[p, l, n] for (p, l), n in sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))]))
    return s


def _type(f):
    t = f.get("type")
    if t in ("string", "textarea", "url", "email", "phone", "encryptedstring") and f.get("length"):
        t = f"{t}({f['length']})"
    elif t in ("double", "currency", "percent") and f.get("precision"):
        t = f"{t}({f['precision']},{f.get('scale', 0)})"
    elif t == "reference" and f.get("referenceTo"):
        t = "reference → " + ", ".join(f["referenceTo"])
    if f.get("calculated"):
        t += " · formula"
    return t


def data_dictionary(snap):
    s = Section("dictionary", "Data dictionary",
                "Every field of each custom object, and the custom fields of each standard object that was described.")
    files = sorted(Path(snap.folder / "objects-config").glob("describe-*.json"))
    custom_first = []
    for f in files:
        name = f.stem[len("describe-"):]
        d = _try(lambda: snap.load("objects-config", f.stem))
        s.sources.append(("objects-config", f.stem))
        if d:
            custom_first.append((not d.get("custom"), name, d))
    for _, name, d in sorted(custom_first):
        fields = d.get("fields", [])
        shown = fields if d.get("custom") else [f for f in fields if f.get("custom")]
        required = lambda f: "yes" if (not f.get("nillable") and f.get("createable") and not f.get("defaultedOnCreate")) else ""
        caption = f"{d.get('label')} ({name}) — {'custom' if d.get('custom') else 'standard'} object, {len(fields)} fields"
        if not d.get("custom"):
            caption += f"; {len(shown)} custom shown"
        rows = [[f.get("name"), f.get("label"), _type(f), required(f)] for f in shown]
        s.tables.append((caption, ["Field", "Label", "Type", "Required"], rows or [["—", "No custom fields", "", ""]]))
    if not custom_first:
        s.notes.append("No object descriptions in this snapshot. Collect objects-config with --describe-custom.")
    return s


def permissions(snap):
    s = Section("permissions", "Permission matrix",
                "Who can do what on the documented objects. R read · C create · E edit · D delete · "
                "V view all · M modify all. Profiles appear as “Profile: …”.")
    objects = sorted(p.stem[len("describe-"):] for p in Path(snap.folder / "objects-config").glob("describe-*.json"))
    sets = {r["Id"]: r for r in _records(snap, "permissions", "permission-sets", s)}
    grid = defaultdict(dict)
    for r in _records(snap, "permissions", "object-permissions", s):
        if r.get("SobjectType") in objects and r.get("ParentId") in sets:
            letters = "".join(l for l, f in ACCESS if r.get(f))
            if letters:
                grid[r["ParentId"]][r["SobjectType"]] = letters
    rows = sorted(([_ps_name(sets[pid])] + [cells.get(o, "") for o in objects] for pid, cells in grid.items()),
                  key=lambda row: row[0].lower())
    if objects:
        s.tables.append(("Object access", ["Permission set / profile"] + objects, rows))
    assigned = Counter(r.get("PermissionSetId") for r in _records(snap, "permissions", "assignments", s))
    admin_rows = []
    for pid, ps in sets.items():
        marks = ["✓" if ps.get(f) else "" for _, f in ADMIN_PERMISSIONS]
        if any(marks):
            admin_rows.append([_ps_name(ps)] + marks + [assigned.get(pid, 0)])
    admin_rows.sort(key=lambda r: (-r[-1], r[0].lower()))
    s.tables.append(("Admin-level permissions", ["Permission set / profile"] + [n for n, _ in ADMIN_PERMISSIONS] + ["Users assigned"],
                     admin_rows))
    return s


def automations(snap):
    s = Section("automations", "Automation map",
                "What runs on each object, and the state of flows and Apex.")
    flows = _records(snap, "automations", "flows", s)
    triggers = _records(snap, "automations", "apex-triggers", s)
    wfr = _records(snap, "automations", "workflow-rules", s)
    classes = _records(snap, "automations", "apex-classes", s)
    per = defaultdict(lambda: defaultdict(list))
    for t in triggers:
        per[t.get("TableEnumOrId")]["Apex triggers"].append(t.get("Name") + ("" if t.get("Status") == "Active" else " (inactive)"))
    for f in flows:
        obj = f.get("TriggerObjectOrEventLabel")
        if obj and f.get("IsActive"):
            kind = "Process Builder" if f.get("ProcessType") == "Workflow" else "Record-triggered flows"
            per[obj][kind].append(f.get("ApiName"))
    for w in wfr:
        per[w.get("TableEnumOrId")]["Workflow rules"].append(w.get("Name"))
    kinds = ["Apex triggers", "Record-triggered flows", "Process Builder", "Workflow rules"]
    s.tables.append(("Automation by object", ["Object"] + kinds,
                     [[obj] + [", ".join(sorted(per[obj][k])) for k in kinds] for obj in sorted(per)]))
    types = Counter((f.get("ProcessType"), bool(f.get("IsActive"))) for f in flows)
    s.tables.append(("Flows by type", ["Type", "Active", "Inactive"],
                     [[t, types[(t, True)], types[(t, False)]] for t in sorted({t for t, _ in types})]))
    own = [c for c in classes if not c.get("NamespacePrefix")]
    old = sorted((c for c in own if (c.get("ApiVersion") or 0) < OLD_API_VERSION), key=lambda c: c.get("ApiVersion") or 0)
    vers = [c.get("ApiVersion") for c in own if c.get("ApiVersion")]
    s.notes.append(f"{len(own)} Apex classes outside managed packages"
                   + (f", API versions {min(vers)} to {max(vers)}" if vers else "") + ".")
    if old:
        s.tables.append((f"Apex classes below API version {OLD_API_VERSION} (review)", ["Class", "API version"],
                         [[c.get("Name"), c.get("ApiVersion")] for c in old]))
    return s


def limits(snap):
    s = Section("limits", "Limits", "The org limits closest to their maximum.")
    s.sources.append(("limits", "limits"))
    rows = []
    for r in _try(lambda: snap.load("limits", "limits"), []) or []:
        mx, rem = r.get("max") or 0, r.get("remaining") or 0
        if mx > 0:
            rows.append((round(100 * (mx - rem) / mx, 1), r.get("name"), mx, mx - rem))
    rows.sort(key=lambda r: (-r[0], r[1]))
    s.tables.append((None, ["Limit", "Max", "Used", "Used %"], [[n, mx, used, f"{pct}%"] for pct, n, mx, used in rows[:15]]))
    return s


def methodology(snap, sections):
    s = Section("method", "Appendix: methodology",
                "Every section above was built by code from the read-only snapshot below. "
                "This table lists where each section's data came from.")
    commands = {}
    for area in ("licenses-users", "permissions", "objects-config", "automations", "limits"):
        for f in (snap.manifest(area) or {}).get("files", []):
            commands[(area, f["file"][: -len(".json")] if f["file"].endswith(".json") else f["file"])] = f
    rows = []
    for sec in sections:
        for area, name in dict.fromkeys(sec.sources):
            f = commands.get((area, name), {})
            rows.append([sec.title, f"{area}/{name}.json", f.get("status", "missing"), f.get("command") or "—"])
    s.intro += f" Snapshot: `{snap.folder.as_posix()}`."
    s.tables.append((None, ["Section", "File", "Status", "Command"], rows))
    return s


def build(snapshot_folder):
    snap = Snapshot(snapshot_folder)
    sections = [overview(snap), licenses_users(snap), data_dictionary(snap), permissions(snap),
                automations(snap), limits(snap)]
    sections.append(methodology(snap, sections))
    return snap, sections


# ---------------------------------------------------------------- renderers
def _md_cell(v):
    return str("" if v is None else v).replace("|", "\\|").replace("\n", " ")


def to_markdown(snap, sections):
    out = [f"# Org documentation — {snap.folder.parent.name}", "",
           f"Built by code from snapshot `{snap.folder.as_posix()}`.", "", "## Contents", ""]
    out += [f"- [{s.title}](#{s.id})" for s in sections] + [""]
    for s in sections:
        out += [f'<a id="{s.id}"></a>', f"## {s.title}", ""]
        if s.intro:
            out += [s.intro, ""]
        out += [n for n in s.notes] + ([""] if s.notes else [])
        for caption, headers, rows in s.tables:
            if caption:
                out += [f"### {caption}", ""]
            out += ["| " + " | ".join(headers) + " |", "|" + " --- |" * len(headers)]
            out += ["| " + " | ".join(_md_cell(v) for v in row) + " |" for row in rows] or []
            if not rows:
                out += ["| " + " | ".join(["—"] + [""] * (len(headers) - 1)) + " |"]
            out.append("")
    return "\n".join(out) + "\n"


def to_html(snap, sections):
    from html import escape
    from checks.html_report import CSS
    extra = ("table.wide{font-size:12.5px}table.wide td,table.wide th{padding:6px 8px}"
             ".toc{columns:2;padding-left:18px}h3{margin:22px 0 8px}"
             "@media print{h3{break-after:avoid}}")
    parts = ['<p class="kicker">Org documentation</p>', f"<h1>{escape(snap.folder.parent.name)}</h1>",
             f'<p class="meta">Built by code from snapshot <code>{escape(snap.folder.as_posix())}</code></p>',
             '<ul class="toc">' + "".join(f'<li><a href="#{s.id}">{escape(s.title)}</a></li>' for s in sections) + "</ul>"]
    for s in sections:
        parts.append(f'<h2 id="{s.id}">{escape(s.title)}</h2>')
        if s.intro:
            parts.append(f"<p>{escape(s.intro)}</p>")
        parts += [f'<p class="note">{escape(n)}</p>' for n in s.notes]
        for caption, headers, rows in s.tables:
            if caption:
                parts.append(f"<h3>{escape(caption)}</h3>")
            wide = ' class="wide"' if len(headers) > 4 else ""
            body = "".join("<tr>" + "".join(f"<td>{escape(str('' if v is None else v))}</td>" for v in row) + "</tr>"
                           for row in rows) or f'<tr><td colspan="{len(headers)}">—</td></tr>'
            parts.append(f"<table{wide}><thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in headers)
                         + f"</tr></thead><tbody>{body}</tbody></table>")
    parts.append("<footer>Built by code from a read-only snapshot. Users are counted, never named. "
                 "Org Assessment · github.com/csilva86/org-assessment</footer>")
    return ("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>Org documentation — {escape(snap.folder.parent.name)}</title>"
            f"<style>{CSS}{extra}</style></head><body><main>{''.join(parts)}</main></body></html>\n")
