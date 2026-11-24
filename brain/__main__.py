"""
Usage:
    python -m brain check [<file> ...]           validate patterns and scan them for client data
    python -m brain list                         list the approved patterns
    python -m brain approve <proposal> --by "<name>"

`check` with no files checks every file in brain/proposals/ and brain/patterns/; a folder
stands for the .yaml files in it.
`approve` is run by the consultant, in their own terminal: it shows the proposal and its
findings, asks the consultant to type the pattern id, stamps approved_by / approved_on and moves
the file to brain/patterns/. Claude cannot run it (the guard_brain hook blocks it, and it refuses
to run without an interactive terminal).

Exit codes: 0 ok, 1 findings or invalid file, 2 refused.
"""
import argparse
import datetime
import sys
from pathlib import Path

import yaml

from .pattern import PatternError, load, validate
from .privacy import scan, sensitive_terms

REPO = Path(__file__).resolve().parents[1]


def _folders(repo):
    return repo / "brain" / "proposals", repo / "brain" / "patterns"


def _print_findings(findings, out):
    for level, field, message in findings:
        print(f"  {'BLOCK' if level == 'block' else 'WARN '} {field}: {message}", file=out)


def check(files, repo=REPO, out=None):
    out = out or sys.stdout
    if not files:
        files = list(_folders(repo))
    # A folder stands for the pattern files in it: `python -m brain check brain/proposals`.
    files = [f for p in map(Path, files) for f in (sorted(p.glob("*.yaml")) if p.is_dir() else [p])]
    terms = sensitive_terms(repo)
    bad = 0
    for path in files:
        try:
            data = load(path)
        except PatternError as e:
            print(f"INVALID {e}", file=out)
            bad += 1
            continue
        findings = scan(data, terms)
        blocks = [f for f in findings if f[0] == "block"]
        print(f"{'BLOCKED' if blocks else 'OK     '} {Path(path).as_posix()} ({data['status']}, {data['kind']})", file=out)
        _print_findings(findings, out)
        bad += bool(blocks)
    print(f"{len(files)} file(s), {bad} with problems", file=out)
    return 1 if bad else 0


def list_patterns(repo=REPO, out=None):
    out = out or sys.stdout
    _, patterns = _folders(repo)
    files = sorted(patterns.glob("*.yaml"))
    for path in files:
        try:
            data = load(path)
        except PatternError as e:
            print(f"INVALID {e}", file=out)
            continue
        if data["status"] != "approved":
            continue
        tags = ", ".join(data.get("tags") or [])
        print(f"{data['id']} [{data['kind']}] {data['title']}", file=out)
        if data.get("applies_when"):
            print(f"    when: {data['applies_when']}", file=out)
        if tags:
            print(f"    tags: {tags}", file=out)
    if not files:
        print("No approved patterns yet.", file=out)
    return 0


def _interactive_confirm(pattern_id):
    if not sys.stdin.isatty():
        return None
    answer = input(f"Type the pattern id ({pattern_id}) to approve it, or press Enter to cancel: ")
    return answer.strip() == pattern_id


def approve(proposal, by, repo=REPO, today=None, confirm=None, out=None):
    """Approve one proposal. `confirm(pattern_id)` returns True/False, or None when nobody can answer."""
    out = out or sys.stdout
    confirm = confirm or _interactive_confirm
    proposal = Path(proposal).resolve()
    proposals, patterns = _folders(repo)
    if proposal.parent != proposals.resolve():
        print(f"Not approved: {proposal} is not in brain/proposals/.", file=out)
        return 2
    if not (by or "").strip():
        print("Not approved: say who approves with --by \"<your name>\".", file=out)
        return 2
    try:
        data = load(proposal)
    except PatternError as e:
        print(f"Not approved: {e}", file=out)
        return 1
    if data["status"] != "proposed":
        print(f"Not approved: status is '{data['status']}', expected 'proposed'.", file=out)
        return 2
    findings = scan(data, sensitive_terms(repo))
    blocks = [f for f in findings if f[0] == "block"]
    print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), file=out)
    _print_findings(findings, out)
    if blocks:
        print("Not approved: the proposal has client data (guardrail 2). Fix the BLOCK lines first.", file=out)
        return 1
    target = patterns / proposal.name
    if target.exists():
        print(f"This replaces the approved pattern {target.name}.", file=out)
    answer = confirm(data["id"])
    if answer is None:
        print("Not approved: approval needs a person at an interactive terminal (guardrail 3).", file=out)
        return 2
    if not answer:
        print("Cancelled. Nothing changed.", file=out)
        return 1
    data["status"] = "approved"
    data["approved_by"] = by.strip()
    data["approved_on"] = (today or datetime.date.today()).isoformat()
    validate(data, target)
    patterns.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    proposal.unlink()
    print(f"Approved: {target.relative_to(repo).as_posix()}", file=out)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m brain")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="validate and scan patterns")
    c.add_argument("files", nargs="*")
    sub.add_parser("list", help="list approved patterns")
    a = sub.add_parser("approve", help="approve a proposal (consultant only)")
    a.add_argument("proposal")
    a.add_argument("--by", required=True)
    args = parser.parse_args(argv)
    if args.command == "check":
        return check(args.files)
    if args.command == "list":
        return list_patterns()
    return approve(args.proposal, args.by)


if __name__ == "__main__":
    sys.exit(main())
