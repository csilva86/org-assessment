#!/usr/bin/env python3
"""
Guardrail 1 — READ-ONLY.

Claude Code runs this script before every Bash command and every Salesforce MCP tool call
(see .claude/settings.json). It blocks anything that could change the org.

How it decides:
- `sf` commands are checked against an ALLOWLIST of read-only commands. Anything not on the
  list is blocked, so a new or unknown command is blocked by default (fail closed).
- `sfdx` (the legacy CLI) is always blocked: use `sf`.
- Raw HTTP calls to Salesforce hosts are blocked unless they are plain GET requests.
- MCP tools whose name suggests a write (deploy, create, update, delete...) are blocked.

Exit codes (Claude Code hook contract):
- 0 → allowed
- 2 → blocked; the message on stderr is shown to Claude
"""
import json
import re
import shlex
import sys

# `sf` commands that only read from the org (or only change local files).
# Each entry is the sequence of subcommand words after `sf`.
READ_ONLY_SF_COMMANDS = [
    ("org", "display"),
    ("org", "list", "limits"),
    ("org", "list", "metadata-types"),
    ("org", "list", "metadata"),
    ("org", "list", "users"),
    ("org", "list"),
    ("org", "login"),          # authentication only, does not change the org
    ("data", "query"),
    ("sobject", "describe"),
    ("sobject", "list"),
    ("project", "retrieve", "start"),  # copies metadata FROM the org to local files
    ("limits", "api", "display"),
    ("api", "request", "rest"),        # allowed only as GET (checked below)
]

# Words that, in an MCP tool name, mean the tool can change something.
MCP_WRITE_WORDS = re.compile(
    r"(deploy|create|insert|update|upsert|delete|remove|destroy|write|execute|run_?apex|anonymous|assign|activate|deactivate|reset|import)",
    re.IGNORECASE,
)

SALESFORCE_HOST = re.compile(r"(salesforce\.com|force\.com|salesforce-setup\.com|cloudforce\.com)", re.IGNORECASE)
HTTP_WRITE = re.compile(r"(-X\s*(POST|PUT|PATCH|DELETE)|--request\s+(POST|PUT|PATCH|DELETE)|-Method\s+(Post|Put|Patch|Delete)|\s(-d|--data\S*|-F|--form|-Body)\s)", re.IGNORECASE)

# Splits a command line into the pieces that run separately: a && b ; c | d
SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")


def block(reason: str) -> None:
    print(f"BLOCKED by read-only guardrail: {reason}", file=sys.stderr)
    sys.exit(2)


def words_of(segment: str) -> list:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        # Unbalanced quotes or similar: we cannot read it reliably, so do not trust it.
        return None


def check_sf(words: list, segment: str) -> None:
    """`words[0]` is `sf`. Allow only the read-only commands above."""
    args = [w for w in words[1:]]
    subcommands = [w for w in args if not w.startswith("-")]

    # `sf`, `sf --version`, `sf help ...`, `sf <anything> --help` are harmless
    if not subcommands or subcommands[0] in ("help", "version", "which") or "--help" in args or "-h" in args:
        return

    # Also accept the colon style: `sf org:list:limits`
    if ":" in subcommands[0]:
        subcommands = subcommands[0].split(":") + subcommands[1:]

    for allowed in READ_ONLY_SF_COMMANDS:
        if tuple(subcommands[: len(allowed)]) == allowed:
            if allowed == ("api", "request", "rest"):
                method = None
                for i, w in enumerate(args):
                    if w in ("--method", "-X") and i + 1 < len(args):
                        method = args[i + 1]
                    elif w.startswith("--method="):
                        method = w.split("=", 1)[1]
                if method and method.upper() != "GET":
                    block(f"`sf api request rest` with method {method} can change the org. Only GET is allowed.")
                if any(w in ("--body", "-b") or w.startswith("--body=") for w in args):
                    block("`sf api request rest` with a body can change the org. Only GET is allowed.")
            return

    block(
        f"`sf {' '.join(subcommands)}` is not on the read-only allowlist. "
        "The assessment never changes the org. If this command only reads, add it to "
        "READ_ONLY_SF_COMMANDS in .claude/hooks/guard_readonly.py and add a test."
    )


def check_bash(command: str) -> None:
    for segment in SEGMENT_SPLIT.split(command or ""):
        segment = segment.strip()
        if not segment:
            continue
        words = words_of(segment)
        if words is None:
            if re.search(r"\bsfdx?\b", segment) or SALESFORCE_HOST.search(segment):
                block("could not parse a command that touches Salesforce.")
            continue
        if not words:
            continue
        # skip leading environment assignments: FOO=bar sf ...
        while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            words = words[1:]
        if not words:
            continue
        program = words[0].rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
        if program.endswith(".exe") or program.endswith(".cmd"):
            program = program.rsplit(".", 1)[0]
        if program == "sfdx":
            block("the legacy `sfdx` CLI is not allowed. Use the read-only `sf` commands.")
        if program == "sf":
            check_sf(words, segment)
        if SALESFORCE_HOST.search(segment) and HTTP_WRITE.search(" " + segment + " "):
            block("an HTTP call that writes to a Salesforce host. Only GET requests are allowed.")


def check_mcp(tool_name: str) -> None:
    # tool names look like mcp__<server>__<tool>
    tool = tool_name.split("__")[-1]
    if MCP_WRITE_WORDS.search(tool):
        block(f"the MCP tool `{tool_name}` looks like it writes to the org.")


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        block("could not read the hook input.")
        return
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool_name in ("Bash", "PowerShell"):
        check_bash(tool_input.get("command", ""))
    elif tool_name.startswith("mcp__"):
        check_mcp(tool_name)
    sys.exit(0)


if __name__ == "__main__":
    main()
