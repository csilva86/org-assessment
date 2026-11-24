"""
Tests for the second brain: pattern format, the client-data scan (guardrail 2), the approval flow
and the guard_brain hook (guardrail 3). Fictional data only.
"""
import datetime
import json
import pathlib
import shutil
import subprocess
import sys

import pytest
import yaml

from brain.__main__ import approve, check, list_patterns
from brain.pattern import PatternError, validate
from brain.privacy import scan, sensitive_terms

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "snapshot-basic"
HOOK = ROOT / ".claude" / "hooks" / "guard_brain.py"

GOOD = {
    "id": "sla-needs-entitlements",
    "kind": "rule-to-checks",
    "title": "SLA rules need entitlements and milestones",
    "status": "proposed",
    "proposed_on": "2026-11-24",
    "tags": ["service", "sla"],
    "applies_when": "A business rule sets response or resolution times on cases.",
    "seen_in_projects": 1,
    "checks": [
        {"area": "objects-config", "what": "Entitlement and CaseMilestone exist.", "how": "code",
         "severity": "high", "rule": {"type": "objects_exist", "objects": ["Case", "Entitlement", "CaseMilestone"]}},
        {"area": "licenses-users", "what": "Enough support licenses are free.", "how": "code", "severity": "high",
         "rule": {"type": "licenses_available", "licenses": ["<license>"], "min_available": "<min_available>"}},
        {"area": "permissions", "what": "Agents can edit <custom_object> records.", "how": "judgement",
         "severity": "medium"},
    ],
}


def pattern(**changes):
    data = json.loads(json.dumps(GOOD))
    data.update(changes)
    return data


@pytest.fixture
def repo(tmp_path):
    """A fake repo: one snapshot, one requirements file, empty brain folders."""
    snap = tmp_path / "snapshots" / "AcmeFixtureAlias" / "2026-01-01_0000"
    shutil.copytree(FIXTURE, snap)
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements" / "acme-rollout.yaml").write_text(yaml.safe_dump({
        "project": "acme-rollout", "status": "draft",
        "rules": [{"id": "BR-01", "checks": [{"id": "BR-01.1", "rule": {
            "type": "object_access", "permission_sets": ["Acme_Agents", "Standard User"], "object": "Case"}}]}],
    }), encoding="utf-8")
    (tmp_path / "brain" / "proposals").mkdir(parents=True)
    (tmp_path / "brain" / "patterns").mkdir(parents=True)
    return tmp_path


def write(folder, data):
    path = folder / f"{data['id']}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


# --- format ---------------------------------------------------------------------------------

def test_good_pattern_is_valid():
    validate(pattern(), "sla-needs-entitlements.yaml")


@pytest.mark.parametrize("changes, message", [
    ({"id": "SLA Entitlements"}, "id must be"),
    ({"kind": "story"}, "kind must be"),
    ({"status": "approved"}, "approved_by"),
    ({"approved_by": "Someone"}, "cannot carry an approval"),
    ({"checks": []}, "needs 'checks'"),
    ({"seen_in_projects": 0}, "seen_in_projects"),
])
def test_invalid_patterns(changes, message):
    with pytest.raises(PatternError, match=message):
        validate(pattern(**changes), f"{pattern(**changes)['id']}.yaml")


def test_file_name_must_be_the_id():
    with pytest.raises(PatternError, match="file name"):
        validate(pattern(), "other.yaml")


def test_check_ids_belong_to_requirements_not_patterns():
    data = pattern()
    data["checks"][0]["id"] = "BR-01.1"
    with pytest.raises(PatternError, match="no 'id'"):
        validate(data, "sla-needs-entitlements.yaml")


def test_numbers_in_a_rule_must_be_placeholders():
    data = pattern()
    data["checks"][1]["rule"]["min_available"] = 50
    with pytest.raises(PatternError, match="<min_available>"):
        validate(data, "sla-needs-entitlements.yaml")


def test_unknown_rule_type_is_rejected():
    data = pattern()
    data["checks"][0]["rule"]["type"] = "objects_are_nice"
    with pytest.raises(PatternError, match="rule whose type"):
        validate(data, "sla-needs-entitlements.yaml")


# --- client-data scan (guardrail 2) ---------------------------------------------------------

def blocks(data, terms=()):
    return [m for level, _, m in scan(data, terms) if level == "block"]


def test_clean_pattern_has_no_blocks():
    assert blocks(pattern()) == []


@pytest.mark.parametrize("text, found", [
    ("Seen on record 0015g00000XyZ12AAB.", "record id"),
    ("Ask ana@acme.example.com first.", "email"),
    ("Log in at acme.my.salesforce.com.", "org address"),
    ("Agents need access to Pedido__c.", "custom API name"),
    ("The Order_Status__mdt type drives it.", "custom API name"),
])
def test_client_data_is_blocked(text, found):
    assert any(found in m for m in blocks(pattern(lesson=text)))


def test_placeholders_are_not_custom_api_names():
    assert blocks(pattern(applies_when="Rules about <custom_object> and <permission_set>.")) == []


def test_numbers_in_text_are_warnings_not_blocks():
    findings = scan(pattern(applies_when="Orgs with 40 agents or more."))
    assert [level for level, _, _ in findings] == ["warn"]


def test_approval_fields_are_not_scanned():
    data = pattern(status="approved", approved_by="Ana Fictícia", approved_on="2026-11-24")
    assert blocks(data, ["Ana Fictícia"]) == []


def test_sensitive_terms_come_from_local_snapshots_and_requirements(repo):
    terms = sensitive_terms(repo)
    for name in ["AcmeFixtureAlias", "Fixture Org", "Ana Fictícia", "Library Book", "acme-rollout", "Acme_Agents"]:
        assert name in terms
    assert "Standard User" not in terms      # a Salesforce profile, not the client's


def test_names_from_the_org_are_blocked(repo):
    terms = sensitive_terms(repo)
    found = blocks(pattern(lesson="In the Fixture Org, Bruno Inventado owned every Library Book."), terms)
    assert len(found) == 3


def test_system_users_are_not_terms(tmp_path):
    users = tmp_path / "snapshots" / "x" / "t" / "licenses-users"
    users.mkdir(parents=True)
    (users / "users.json").write_text(json.dumps({"status": 0, "result": {"records": [
        {"Name": "Automated Process", "UserType": "AutomatedProcess"},
        {"Name": "Real Person", "UserType": "Standard"}]}}), encoding="utf-8")
    terms = sensitive_terms(tmp_path)
    assert "Real Person" in terms and "Automated Process" not in terms


# --- check, list, approve -------------------------------------------------------------------

def test_check_reports_blocked_proposals(repo, capsys):
    write(repo / "brain" / "proposals", pattern(lesson="Fixture Org had no SLA."))
    assert check([], repo=repo) == 1
    assert "BLOCKED" in capsys.readouterr().out


def test_check_accepts_a_folder(repo, capsys):
    write(repo / "brain" / "proposals", pattern())
    assert check([str(repo / "brain" / "proposals")], repo=repo) == 0
    assert "1 file(s), 0 with problems" in capsys.readouterr().out


def test_approve_moves_and_stamps(repo):
    proposal = write(repo / "brain" / "proposals", pattern())
    code = approve(proposal, "Carlos Silva", repo=repo, today=datetime.date(2026, 11, 24),
                   confirm=lambda pid: True, out=open(repo / "out.txt", "w"))
    assert code == 0
    assert not proposal.exists()
    saved = yaml.safe_load((repo / "brain" / "patterns" / "sla-needs-entitlements.yaml").read_text(encoding="utf-8"))
    assert (saved["status"], saved["approved_by"], saved["approved_on"]) == ("approved", "Carlos Silva", "2026-11-24")


def test_approve_needs_a_person(repo):
    proposal = write(repo / "brain" / "proposals", pattern())
    code = approve(proposal, "Carlos Silva", repo=repo, confirm=lambda pid: None, out=open(repo / "o", "w"))
    assert code == 2 and proposal.exists()


def test_approve_can_be_cancelled(repo):
    proposal = write(repo / "brain" / "proposals", pattern())
    assert approve(proposal, "Carlos Silva", repo=repo, confirm=lambda pid: False, out=open(repo / "o", "w")) == 1
    assert proposal.exists()


def test_approve_refuses_client_data(repo):
    proposal = write(repo / "brain" / "proposals", pattern(lesson="Seen in AcmeFixtureAlias."))
    asked = []
    code = approve(proposal, "Carlos Silva", repo=repo, confirm=asked.append, out=open(repo / "o", "w"))
    assert code == 1 and asked == [] and proposal.exists()


def test_approve_only_from_proposals(repo):
    elsewhere = write(repo, pattern())
    assert approve(elsewhere, "Carlos Silva", repo=repo, confirm=lambda pid: True, out=open(repo / "o", "w")) == 2


def test_approve_without_a_terminal_is_refused(repo):
    """Run as Claude would: no interactive terminal, so nobody can type the id."""
    proposal = write(repo / "brain" / "proposals", pattern())
    code = approve(proposal, "Carlos Silva", repo=repo, out=open(repo / "o", "w"))
    assert code == 2 and proposal.exists()


def test_list_shows_only_approved(repo, capsys):
    write(repo / "brain" / "patterns", pattern(status="approved", approved_by="C", approved_on="2026-11-24"))
    list_patterns(repo=repo)
    assert "sla-needs-entitlements [rule-to-checks]" in capsys.readouterr().out


def test_committed_patterns_are_clean():
    """Every pattern in the repository passes the format and the scan."""
    for path in (ROOT / "brain" / "patterns").glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        validate(data, path)
        assert data["status"] == "approved"
        assert blocks(data) == []


# --- guard_brain hook (guardrail 3) ---------------------------------------------------------

def run_hook(tool_name, tool_input):
    event = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input,
             "cwd": "C:/Users/demo/OneDrive/Área de Trabalho/OrgAssessment"}
    result = subprocess.run([sys.executable, str(HOOK)], capture_output=True,
                            input=json.dumps(event, ensure_ascii=False).encode("utf-8"))
    return result.returncode


@pytest.mark.parametrize("command", [
    'python -m brain approve brain/proposals/x.yaml --by "Carlos"',
    'py -m brain approve brain\\proposals\\x.yaml --by "Carlos"',
    "cd repo && python -m brain approve brain/proposals/x.yaml --by C",
    "mv brain/proposals/x.yaml brain/patterns/x.yaml",
    "cp brain/proposals/x.yaml brain\\patterns\\x.yaml",
    "cat brain/proposals/x.yaml > brain/patterns/x.yaml",
    "rm brain/patterns/x.yaml",
    "sed -i s/proposed/approved/ brain/patterns/x.yaml",
    "Move-Item brain\\proposals\\x.yaml brain\\patterns\\x.yaml",
    "Set-Content -Path brain/patterns/x.yaml -Value x",
    "git checkout -- brain/patterns",
])
def test_hook_blocks(command):
    assert run_hook("Bash", {"command": command}) == 2


@pytest.mark.parametrize("command", [
    "python -m brain check brain/proposals",
    "python -m brain check brain/patterns/x.yaml",
    "python -m brain list",
    "cat brain/patterns/x.yaml",
    "ls brain/patterns",
    "Get-Content brain\\patterns\\x.yaml",
    "grep -r sla brain/patterns",
    "python -m pytest tests",
])
def test_hook_allows(command):
    assert run_hook("Bash", {"command": command}) == 0


@pytest.mark.parametrize("tool, path, code", [
    ("Write", "C:\\Users\\demo\\OrgAssessment\\brain\\patterns\\x.yaml", 2),
    ("Edit", "/home/demo/OrgAssessment/brain/patterns/x.yaml", 2),
    ("Write", "brain/patterns/x.yaml", 2),
    ("Write", "C:\\Users\\demo\\OrgAssessment\\brain\\proposals\\x.yaml", 0),
    ("Edit", "requirements/demo.yaml", 0),
])
def test_hook_on_file_tools(tool, path, code):
    assert run_hook(tool, {"file_path": path}) == code
