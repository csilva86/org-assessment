"""
Usage:
    python -m checks run <requirements.yaml> <snapshot-folder> [--out <results.json>]

Default output: reports/<alias>/<timestamp>/results.json, mirroring the snapshot path
(snapshots/<alias>/<timestamp>). `reports/` is git-ignored: results hold org data.
"""
import argparse
import json
import sys
from pathlib import Path

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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m checks")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run the checks of an approved requirements file on a snapshot")
    r.add_argument("requirements")
    r.add_argument("snapshot")
    r.add_argument("--out")
    args = parser.parse_args(argv)

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
