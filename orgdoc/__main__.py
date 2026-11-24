"""
Usage:
    python -m orgdoc build <snapshots/alias/timestamp> [--out <folder>] [--pdf]

Writes org-documentation.md and .html (and .pdf with --pdf) into reports/<alias>/<timestamp>/
by default. `reports/` is git-ignored: the documentation holds org data.
"""
import argparse
import sys
from pathlib import Path

from checks.__main__ import default_out
from checks.pdf import to_pdf
from checks.snapshot import SnapshotError

from .build import build, to_html, to_markdown


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m orgdoc")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="build the org documentation from a snapshot")
    b.add_argument("snapshot")
    b.add_argument("--out")
    b.add_argument("--pdf", action="store_true")
    args = parser.parse_args(argv)
    try:
        snap, sections = build(args.snapshot)
    except SnapshotError as e:
        print(f"Not built: {e}", file=sys.stderr)
        return 2
    folder = Path(args.out) if args.out else default_out(args.snapshot).parent
    folder.mkdir(parents=True, exist_ok=True)
    md, html = folder / "org-documentation.md", folder / "org-documentation.html"
    md.write_text(to_markdown(snap, sections), encoding="utf-8")
    html.write_text(to_html(snap, sections), encoding="utf-8")
    print(f"Written: {md}\nWritten: {html}")
    if args.pdf:
        try:
            print(f"Written: {to_pdf(html, html.with_suffix('.pdf'))}")
        except RuntimeError as e:
            print(f"PDF not written: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
