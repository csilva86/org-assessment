"""
Usage:
    python -m checks run <requirements.yaml> <snapshot-folder> [--out <results.json>] [--pdf]
    python -m checks report <results.json> [--pdf]

`run` writes results.json and, next to it, the reports: client-summary.md/.html,
consultant-detail.md/.html and gaps.json (plus .pdf files with --pdf, printed by Edge or Chrome).
`report` rebuilds the reports from an existing results.json.

Default output: reports/<alias>/<timestamp>/results.json, mirroring the snapshot path
(snapshots/<alias>/<timestamp>). `reports/` is git-ignored: results hold org data.
"""
import argparse
import json
import sys
from pathlib import Path

from .html_report import write_html
from .pdf import to_pdf
from .report import write_all
from .requirements import RequirementsError
from .runner import run
from .snapshot import SnapshotError

ICONS = {"met": "OK  ", "partial": "PART", "not_met": "FAIL", "needs_judgement": "JUDG", "error": "ERR "}


def default_out(snapshot):
    parts = Path(snapshot).resolve().parts
    if "snapshots" in parts:
        i = parts.index("snapshots")
        return Path(*parts[:i], "reports", *parts[i + 1:], "results.json")
    return Path("reports") / Path(snapshot).name / "results.json"


def write_reports(report, folder, pdf=False):
    files = write_all(report, folder) + write_html(report, folder)
    if pdf:
        for html in [f for f in files if f.suffix == ".html"]:
            try:
                files.append(to_pdf(html, html.with_suffix(".pdf")))
            except RuntimeError as e:
                print(f"PDF not written for {html.name}: {e}", file=sys.stderr)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m checks")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run the checks of an approved requirements file on a snapshot")
    r.add_argument("requirements")
    r.add_argument("snapshot")
    r.add_argument("--out")
    r.add_argument("--pdf", action="store_true", help="also print the HTML reports to PDF")
    rp = sub.add_parser("report", help="rebuild the reports from an existing results.json")
    rp.add_argument("results")
    rp.add_argument("--pdf", action="store_true", help="also print the HTML reports to PDF")
    args = parser.parse_args(argv)

    if args.command == "report":
        path = Path(args.results)
        if not path.exists():
            print(f"Not found: {path}", file=sys.stderr)
            return 2
        report = json.loads(path.read_text(encoding="utf-8"))
        for f in write_reports(report, path.parent, args.pdf):
            print(f"Written: {f}")
        return 0

    try:
        report = run(args.requirements, args.snapshot)
    except (RequirementsError, SnapshotError) as e:
        print(f"Not run: {e}", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else default_out(args.snapshot)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    for res in report["results"]:
        print(f"[{ICONS[res['status']]}] {res['check_id']:<10} {res['severity']:<6} {res['summary']}")
    c = report["counts"]
    print(f"\n{c['met']} met · {c['partial']} partial · {c['not_met']} not met · "
          f"{c['needs_judgement']} need judgement · {c['error']} error(s)")
    print(f"Results: {out}")
    for f in write_reports(report, out.parent, args.pdf):
        print(f"Report:  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
