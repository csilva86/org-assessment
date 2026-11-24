"""
Usage:
    python -m collect area <area> --alias <alias> --snapshot <snapshots/alias/timestamp> [--objects A,B] [--describe-custom]

Runs the area's read-only commands and writes <snapshot>/<area>/*.json, *.stderr.log and
_manifest.json. Exit code 0 when every file is ok (or skipped), 1 when any failed, 2 when refused.
"""
import argparse
import sys

from .plan import AREAS, PlanError
from .runner import CollectError, collect_area


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m collect")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("area", help="collect one area into a snapshot")
    a.add_argument("area", choices=AREAS)
    a.add_argument("--alias", required=True)
    a.add_argument("--snapshot", required=True)
    a.add_argument("--objects", default="", help="comma-separated objects to describe (objects-config)")
    a.add_argument("--describe-custom", action="store_true",
                   help="also describe every custom object found in the org (objects-config)")
    args = parser.parse_args(argv)

    objects = [o.strip() for o in args.objects.split(",") if o.strip()]
    try:
        manifest = collect_area(args.area, args.alias, args.snapshot, objects, describe_custom=args.describe_custom)
    except (CollectError, PlanError) as e:
        print(f"Not collected: {e}", file=sys.stderr)
        return 2
    ok = sum(1 for f in manifest["files"] if f["status"] == "ok")
    failed = [f for f in manifest["files"] if f["status"] == "failed"]
    skipped = sum(1 for f in manifest["files"] if f["status"] == "skipped")
    retried = sum(1 for f in manifest["files"] if f["attempts"] == 2)
    print(f"{args.area}: {ok} ok, {len(failed)} failed, {skipped} skipped, {retried} retried")
    for f in failed:
        print(f"  FAILED {f['file']}: {f['error']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
