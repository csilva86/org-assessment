"""
Tests for the read-only guardrail (.claude/hooks/guard_readonly.py).

Run with:  python -m pytest tests
Every command the assessment needs must be ALLOWED here, and every way of
changing the org we can think of must be BLOCKED. Add a case before you
change the allowlist.
"""
import json
import pathlib
import subprocess
import sys

import pytest

HOOK = pathlib.Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard_readonly.py"


def run_hook(tool_name, tool_input, cwd="C:/Users/demo/OneDrive/Área de Trabalho/Página Empresa/OrgAssessment"):
    # Claude Code sends UTF-8 JSON that includes the working folder, which may have accents.
    event = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(event, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
    )
    return result.returncode, result.stderr.decode("utf-8", errors="replace")


ALLOWED = [
    "sf org list limits --target-org demo --json",
    "sf org list metadata --metadata-type Flow --target-org demo --json",
    "sf org list metadata-types --target-org demo",
    'sf data query --query "SELECT Id, Name, Profile.Name FROM User WHERE IsActive = true" --target-org demo --json',
    'sf data query -q "SELECT Id FROM PermissionSet" --use-tooling-api -o demo --json',
    "sf sobject describe --sobject Case --target-org demo --json",
    "sf sobject list --target-org demo",
    "sf project retrieve start --metadata Flow --target-metadata-dir snapshots/tmp -o demo",
    "sf api request rest /services/data/v62.0/limits --target-org demo",
    "sf api request rest /services/data/v62.0/limits --method GET --target-org demo",
    "sf data query --file queries/licenses-users/users.soql --target-org demo --json",
    "sf data query --file queries/automations/workflow-rules.tooling.soql --use-tooling-api --target-org demo --json",
    "sf --version",
    "SF_LOG_LEVEL=debug sf org list limits -o demo",
    "sf --version 2>&1 | head -1",
    "sf org list limits --target-org demo --json 2>/dev/null > snapshots/demo/limits/limits.json",
    "sf data query --file queries/licenses-users/users.soql -o demo --json 2> /dev/null >snapshots/demo/users.json",
    "sf project deploy start --help",
    "sf org:list:limits -o demo",
    "python -m pytest tests",
    "git status",
    "ls snapshots",
    'sf data query -q "SELECT Id FROM User" -o demo --json > snapshots/demo/users.json',
]

BLOCKED = [
    "sf project deploy start --source-dir force-app -o demo",
    "sf project delete source --metadata ApexClass:Foo -o demo",
    "sf data create record --sobject Account --values \"Name=Test\" -o demo",
    "sf data update record --sobject Account --record-id 001xx --values \"Name=X\" -o demo",
    "sf data delete record --sobject Account --record-id 001xx -o demo",
    "sf data upsert bulk --sobject Account --file a.csv --external-id Id -o demo",
    "sf data import tree --files data.json -o demo",
    "sf apex run --file script.apex -o demo",
    "sf org assign permset --name Admin -o demo",
    "sf org create user -o demo",
    "sf org delete scratch -o demo",
    "sf org logout --all",
    "sf api request rest /services/data/v62.0/sobjects/Account --method POST --body @a.json -o demo",
    "sf api request rest /services/data/v62.0/sobjects/Account -X DELETE -o demo",
    "sf api request graphql --body q.graphql -o demo",
    "sfdx force:source:deploy -p force-app",
    "sf org display -o demo && sf project deploy start -o demo",
    "sf org display -o demo; sf apex run -f x.apex -o demo",
    "curl -X POST https://demo.my.salesforce.com/services/data/v62.0/sobjects/Account -d '{}'",
    "/usr/local/bin/sf project deploy start -o demo",
    "sf.cmd project deploy start -o demo",
    "sf some-new-command -o demo",
    "sf org display --target-org demo --json",
    "sf org display -o demo --verbose",
    "sf org:display -o demo",
    "sf org list auth",
    "sf project deploy start -o demo 2>&1",
    "sf project deploy start -o demo > out.json 2>&1",
    "sf --version 2>&1 && sf apex run -f x.apex -o demo",
]


@pytest.mark.parametrize("command", ALLOWED)
def test_read_only_commands_are_allowed(command):
    code, err = run_hook("Bash", {"command": command})
    assert code == 0, f"should be allowed: {command}\n{err}"


@pytest.mark.parametrize("command", BLOCKED)
def test_write_commands_are_blocked(command):
    code, err = run_hook("Bash", {"command": command})
    assert code == 2, f"should be blocked: {command}"
    assert "BLOCKED" in err


@pytest.mark.parametrize("tool", [
    "mcp__salesforce__deploy_metadata",
    "mcp__salesforce__create_record",
    "mcp__salesforce__run_apex",
    "mcp__salesforce__delete_record",
])
def test_mcp_write_tools_are_blocked(tool):
    code, _ = run_hook(tool, {})
    assert code == 2


@pytest.mark.parametrize("tool", [
    "mcp__salesforce__run_soql_query",
    "mcp__salesforce__describe_sobject",
    "mcp__salesforce__list_limits",
])
def test_mcp_read_tools_are_allowed(tool):
    code, err = run_hook(tool, {})
    assert code == 0, err


def test_unreadable_input_is_blocked():
    result = subprocess.run([sys.executable, str(HOOK)], input=b"not json", capture_output=True)
    assert result.returncode == 2


def test_accented_folder_does_not_break_the_hook():
    code, err = run_hook("Bash", {"command": "sf org list limits -o demo"},
                         cwd="C:/Usuários/José/Área de Trabalho/Página Empresa/Ação")
    assert code == 0, err


def test_credential_commands_explain_why():
    code, err = run_hook("Bash", {"command": "sf org display -o demo --json"})
    assert code == 2
    assert "access token" in err and "organization.soql" in err
