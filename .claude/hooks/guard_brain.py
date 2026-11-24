#!/usr/bin/env python3
"""
Guardrail 3 for the second brain — ONLY THE CONSULTANT APPROVES A PATTERN.

Claude Code runs this script before every Bash, PowerShell, Write and Edit call
(see .claude/settings.json). Claude may draft proposals in brain/proposals/, but it can never:
- run `python -m brain approve` (the consultant runs it in their own terminal);
- write, edit, move or delete anything in brain/patterns/ (approved patterns).

Reading brain/patterns/ is allowed (the Read tool, `python -m brain list|check`, cat, ls, grep...).

Exit codes (Claude Code hook contract): 0 allowed, 2 blocked (stderr is shown to Claude).
"""
import json
import re
import shlex
import sys

APPROVED_DIR = "brain/patterns"
SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
APPROVE = re.compile(r"(?:^|[\s\"'])-m\s+brain(?:\.__main__)?\s+approve\b")
READERS = {"cat", "type", "head", "tail", "less", "more", "ls", "dir", "grep", "rg", "find", "wc",
           "get-content", "gc", "get-childitem", "gci", "select-string", "sls"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


class Blocked(Exception):
    pass


def _norm(text):
    return (text or "").replace("\\", "/").lower()


def _program(segment):
    try:
        words = shlex.split(segment, posix=False)
    except ValueError:
        return None, []
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words = words[1:]
    if not words:
        return "", []
    program = words[0].strip("\"'").rsplit("/", 1)[-1].lower()
    for ext in (".exe", ".cmd", ".bat"):
        if program.endswith(ext):
            program = program[: -len(ext)]
    return program, [w.strip("\"'").lower() for w in words[1:]]


def check_command(command):
    text = _norm(command)
    if APPROVE.search(text):
        raise Blocked("`python -m brain approve` is for the consultant, in their own terminal (guardrail 3). "
                      "Tell the consultant which proposal is ready and the exact command to run.")
    for segment in SEGMENT_SPLIT.split(text):
        if APPROVED_DIR not in segment:
            continue
        program, args = _program(segment)
        if program in ("python", "python3", "py") and args[:2] == ["-m", "brain"] and args[2:3] in (["check"], ["list"]):
            continue
        if program in READERS and ">" not in segment and "-i" not in args:
            continue
        raise Blocked(f"brain/patterns/ holds approved patterns: only `python -m brain approve`, run by the "
                      f"consultant, changes it (guardrail 3). Write proposals to brain/proposals/ instead.")


def check_write(tool_input):
    path = _norm(tool_input.get("file_path") or tool_input.get("notebook_path"))
    if f"/{APPROVED_DIR}/" in f"/{path}" or path.endswith(f"/{APPROVED_DIR}"):
        raise Blocked("brain/patterns/ holds approved patterns: Claude never writes there (guardrail 3). "
                      "Write the proposal to brain/proposals/<id>.yaml; the consultant approves it.")


def main():
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        print("BLOCKED by brain guardrail: could not read the hook input.", file=sys.stderr)
        sys.exit(2)
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    try:
        if tool_name in ("Bash", "PowerShell"):
            check_command(tool_input.get("command", ""))
        elif tool_name in WRITE_TOOLS:
            check_write(tool_input)
    except Blocked as e:
        print(f"BLOCKED by brain guardrail: {e}", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
