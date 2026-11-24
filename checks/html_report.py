"""
HTML reports for delivery, built by code from results.json (same data as the Markdown reports).

Each page is one self-contained file: styles inline, no scripts, no fonts or images from the
internet, so a client report can be opened offline, e-mailed, or printed to PDF as it is.
"""
import json
from html import escape
from pathlib import Path

from .report import AREA_NAMES, GAP_STATUSES, SEVERITY_ORDER, STATUS_LABEL, group_by_rule, recommend

STATUS_CLASS = {"met": "met", "partial": "partial", "not_met": "notmet", "needs_judgement": "review", "error": "error"}

CSS = """
:root{--ink:#1d2330;--muted:#5d6577;--line:#e3e6ec;--soft:#f6f7f9;
--met:#1f7a46;--met-bg:#e6f4ec;--partial:#9a6700;--partial-bg:#fff4d6;--notmet:#b42318;--notmet-bg:#fde8e7;
--review:#3451b2;--review-bg:#e9edfb;--error:#6b4f00;--error-bg:#f3ecd9}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif}
main{max-width:880px;margin:0 auto;padding:48px 40px 64px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
h1{font-size:28px;line-height:1.2;margin:0 0 8px}
h2{font-size:19px;margin:40px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:0 0 6px}
.meta{color:var(--muted);font-size:13px;margin:0 0 28px}
.headline{font-size:20px;margin:0 0 18px}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 8px}
.card{flex:1 1 120px;border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.card b{display:block;font-size:24px;line-height:1.1}
.card span{font-size:12px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line)}
td{padding:10px;border-bottom:1px solid var(--line);vertical-align:top}
.pill{display:inline-block;white-space:nowrap;font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px}
.met{color:var(--met);background:var(--met-bg)}.partial{color:var(--partial);background:var(--partial-bg)}
.notmet{color:var(--notmet);background:var(--notmet-bg)}.review{color:var(--review);background:var(--review-bg)}
.error{color:var(--error);background:var(--error-bg)}
.note{color:var(--muted);font-size:13px}
.bar{height:8px;background:var(--soft);border-radius:4px;overflow:hidden;min-width:120px}
.bar i{display:block;height:100%;background:var(--met)}
ul.attention{padding-left:20px}ul.attention li{margin:6px 0}
.rule{border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:0 0 18px}
.rule>header{display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin:0 0 12px}
.check{border-top:1px solid var(--line);padding:12px 0 4px;break-inside:avoid}
.check dl{display:grid;grid-template-columns:110px 1fr;gap:4px 12px;margin:8px 0 0;font-size:14px}
.check dt{color:var(--muted)}.check dd{margin:0}
code,.ev{font:12.5px/1.5 Consolas,"SFMono-Regular",Menlo,monospace}
.ev{background:var(--soft);border-radius:6px;padding:8px 10px;white-space:pre-wrap;word-break:break-word}
.fix{background:var(--soft);border-left:3px solid var(--review);padding:8px 12px;border-radius:0 6px 6px 0}
footer{margin-top:48px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
@page{size:A4;margin:16mm 14mm}
@media print{main{padding:0;max-width:none}h2,.rule>header{break-after:avoid}tr,.check{break-inside:avoid}
.pill,.bar i,.card{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""


def _pill(status, text=None):
    return f'<span class="pill {STATUS_CLASS[status]}">{escape(text or STATUS_LABEL[status])}</span>'


def _page(title, body):
    return ("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{escape(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{body}</main></body></html>\n")


def _footer():
    return ("<footer>Built by code from the assessment results: every verdict is backed by data "
            "collected read-only from the org. Org Assessment · github.com/csilva86/org-assessment</footer>")


# ---------------------------------------------------------------- client
def client_html(report):
    rules = group_by_rule(report["results"])
    counts = {k: sum(1 for g in rules if g["status"] == k) for k in STATUS_LABEL}
    project = report.get("project") or ""
    parts = [
        '<p class="kicker">Org assessment</p>',
        f"<h1>{escape(project)}</h1>",
        f'<p class="meta">Requirements approved by {escape(str(report.get("approved_by")))} on '
        f'{escape(str(report.get("approved_on")))} · snapshot {escape(Path(report["snapshot"]).name)}</p>',
        f'<p class="headline"><b>{counts["met"]} of {len(rules)}</b> business rules are met.</p>',
        '<div class="cards">',
    ]
    for k in ("met", "partial", "not_met", "error"):
        if k == "met" or counts[k]:
            parts.append(f'<div class="card"><b>{counts[k]}</b><span>{escape(STATUS_LABEL[k])}</span></div>')
    parts.append("</div>")

    parts += ["<h2>Business rules</h2>", "<table><thead><tr><th>Business rule</th><th>Verdict</th></tr></thead><tbody>"]
    for g in rules:
        extra = '<div class="note">One point awaits consultant review.</div>' if g["pending_review"] else ""
        parts.append(f"<tr><td>{escape(g['text'] or '')}{extra}</td><td>{_pill(g['status'])}</td></tr>")
    parts.append("</tbody></table>")

    parts += ["<h2>By area</h2>", "<table><thead><tr><th>Area</th><th>Checks met</th><th></th></tr></thead><tbody>"]
    for area, name in AREA_NAMES.items():
        checks = [r for r in report["results"] if r["area"] == area and r["status"] != "needs_judgement"]
        if checks:
            met = sum(1 for r in checks if r["status"] == "met")
            pct = round(100 * met / len(checks))
            parts.append(f'<tr><td>{escape(name)}</td><td>{met} of {len(checks)}</td>'
                         f'<td><div class="bar"><i style="width:{pct}%"></i></div></td></tr>')
    parts.append("</tbody></table>")

    gaps = sorted((r for r in report["results"] if r["status"] in GAP_STATUSES),
                  key=lambda r: (SEVERITY_ORDER[r["severity"]], r["check_id"]))
    parts.append("<h2>What needs attention</h2>")
    if gaps:
        parts.append('<ul class="attention">')
        for r in gaps:
            parts.append(f"<li><b>{escape(r['what'].rstrip('.'))}</b> — {_pill(r['status'])} "
                         f'<span class="note">{escape(r["severity"])} priority</span></li>')
        parts.append("</ul>")
    else:
        parts.append("<p>Nothing: every check that can be verified by code is met.</p>")
    errors = sum(1 for r in report["results"] if r["status"] == "error")
    if errors:
        parts.append(f'<p class="note">{errors} check(s) could not be assessed because data was missing; '
                     "see the consultant report.</p>")
    parts.append(_footer())
    return _page(f"Org assessment — {project}", "".join(parts))


# ---------------------------------------------------------------- consultant
def _evidence(evidence):
    rows = []
    for ev in evidence or []:
        where = ", ".join(f"{k}={v}" for k, v in (ev.get("where") or {}).items())
        line = ev["file"] + (f"  where {where}" if where else "")
        if "values" in ev:
            line += "\n  " + json.dumps(ev["values"], ensure_ascii=False)
        rows.append(line)
    return f'<div class="ev">{escape(chr(10).join(rows))}</div>' if rows else ""


def consultant_html(report):
    c = report["counts"]
    project = report.get("project") or ""
    parts = [
        '<p class="kicker">Consultant report</p>',
        f"<h1>{escape(project)}</h1>",
        "<table><tbody>",
        f"<tr><td>Requirements</td><td><code>{escape(report['requirements'])}</code><br>"
        f"approved by {escape(str(report.get('approved_by')))} on {escape(str(report.get('approved_on')))}</td></tr>",
        f"<tr><td>Snapshot</td><td><code>{escape(report['snapshot'])}</code></td></tr>",
        f"<tr><td>Generated</td><td>{escape(report['generated_at'])}</td></tr>",
        "<tr><td>Results</td><td>" + " ".join(
            f"{_pill(k, f'{c[k]} {STATUS_LABEL[k].lower()}')}" for k in ("met", "partial", "not_met", "needs_judgement", "error") if c[k]
        ) + "</td></tr></tbody></table>",
    ]
    for g in group_by_rule(report["results"]):
        parts.append(f'<section class="rule"><header><h2 style="border:0;margin:0;padding:0">{escape(g["id"])} · '
                     f'{escape(g["text"] or "")}</h2>{_pill(g["status"])}</header>')
        for r in g["checks"]:
            fix = recommend(r)
            rows = [
                ("Result", escape(r["summary"])),
                ("Priority", f"{escape(r['severity'])} · {escape(AREA_NAMES.get(r['area'], r['area']))} · {escape(r['how'])}"),
            ]
            if r.get("rule"):
                rows.append(("Rule", f"<code>{escape(json.dumps(r['rule'], ensure_ascii=False))}</code>"))
            ev = _evidence(r.get("evidence"))
            if ev:
                rows.append(("Evidence", ev))
            if fix:
                rows.append(("Recommended", f'<div class="fix">{escape(fix)}</div>'))
            dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
            parts.append(f'<div class="check"><h3>{_pill(r["status"])} {escape(r["check_id"])} · '
                         f'{escape(r["what"] or "")}</h3><dl>{dl}</dl></div>')
        parts.append("</section>")
    parts += ["<h2>Method</h2>",
              "<p>Org data was collected read-only into the snapshot above by <code>python -m collect</code>. "
              "Every <code>code</code> check is deterministic Python run on that snapshot; <code>judgement</code> "
              "checks are left to the consultant. Recommendations come from fixed templates per rule type.</p>",
              _footer()]
    return _page(f"Consultant report — {project}", "".join(parts))


def write_html(report, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = {"client-summary.html": client_html(report), "consultant-detail.html": consultant_html(report)}
    for name, text in out.items():
        (folder / name).write_text(text, encoding="utf-8")
    return [folder / n for n in out]
