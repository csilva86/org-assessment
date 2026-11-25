"""
Tests for `python -m collect`, with a fake `sf` (no org is ever contacted in tests).
"""
import json
import re

import pytest

from collect import runner
from collect.__main__ import main
from collect.plan import PlanError, steps
from collect.runner import CollectError, collect_area
from checks.snapshot import Snapshot

KEYS = {"file", "command", "ran_at", "status", "records", "attempts", "error"}


def ok_query(n):
    return json.dumps({"status": 0, "result": {"records": [{"Id": str(i)} for i in range(n)],
                                               "totalSize": n, "done": True}}).encode()


class FakeSf:
    """Answers every command with `answers` in order (the last one repeats)."""
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, args, cwd):
        self.calls.append(args)
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def test_manifest_is_written_by_code(tmp_path):
    fake = FakeSf((0, ok_query(3), b""))
    m = collect_area("licenses-users", "demo", tmp_path / "snap", run=fake, sleep=lambda s: None)
    assert m["collected_by"] == "python -m collect"
    assert len(m["files"]) == 4 and all(set(f) == KEYS for f in m["files"])
    assert all(f["status"] == "ok" and f["records"] == 3 and f["attempts"] == 1 for f in m["files"])
    assert all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", f["ran_at"]) for f in m["files"])
    folder = tmp_path / "snap" / "licenses-users"
    assert (folder / "users.json").exists() and (folder / "users.stderr.log").exists()
    assert json.loads((folder / "_manifest.json").read_text(encoding="utf-8")) == m


def test_every_command_is_read_only_and_json(tmp_path):
    fake = FakeSf((0, ok_query(1), b""))
    for area in ("licenses-users", "permissions", "automations", "limits"):
        collect_area(area, "demo", tmp_path / "snap", run=fake, sleep=lambda s: None)
    collect_area("objects-config", "demo", tmp_path / "snap", objects=["Case"], run=fake, sleep=lambda s: None)
    guard = runner._load_guard()
    for args in fake.calls:
        assert args[0] == "sf" and "--json" in args and "--query" not in args
        assert guard.check_command(" ".join(args)) is None


def test_one_retry_when_sf_fails_without_output(tmp_path):
    waits = []
    fake = FakeSf((1, b"", b"spawn error"), (0, ok_query(2), b""))
    m = collect_area("limits", "demo", tmp_path / "snap", run=fake, sleep=waits.append)
    assert m["files"][0]["status"] == "ok" and m["files"][0]["attempts"] == 2
    assert waits == [runner.RETRY_WAIT_SECONDS] and len(fake.calls) == 2


def test_never_a_second_retry(tmp_path):
    fake = FakeSf((1, b"", b"first line\nERROR: spawn failed\n"))
    m = collect_area("limits", "demo", tmp_path / "snap", run=fake, sleep=lambda s: None)
    f = m["files"][0]
    assert f["status"] == "failed" and f["attempts"] == 2 and f["error"] == "ERROR: spawn failed"
    assert len(fake.calls) == 2


def test_sf_error_message_is_kept_and_not_retried(tmp_path):
    err = json.dumps({"status": 1, "name": "NamedOrgNotFoundError", "message": "No authorization for demo"})
    fake = FakeSf((1, err.encode(), b""))
    m = collect_area("limits", "demo", tmp_path / "snap", run=fake, sleep=lambda s: None)
    assert m["files"][0]["error"] == "No authorization for demo" and m["files"][0]["attempts"] == 1


def test_describes_only_the_objects_given(tmp_path):
    fake = FakeSf((0, json.dumps({"status": 0, "result": {"name": "X"}}).encode(), b""))
    m = collect_area("objects-config", "demo", tmp_path / "a", objects=["Case", "Library_Book__c"],
                     run=fake, sleep=lambda s: None)
    names = [f["file"] for f in m["files"]]
    assert "describe-Case.json" in names and "describe-Library_Book__c.json" in names
    m2 = collect_area("objects-config", "demo", tmp_path / "b", run=fake, sleep=lambda s: None)
    assert m2["files"][-1]["status"] == "skipped"


def test_a_snapshot_is_never_reused(tmp_path):
    fake = FakeSf((0, ok_query(1), b""))
    collect_area("limits", "demo", tmp_path / "snap", run=fake, sleep=lambda s: None)
    with pytest.raises(CollectError, match="Never reuse"):
        collect_area("limits", "demo", tmp_path / "snap", run=fake, sleep=lambda s: None)


def test_write_commands_are_refused_before_anything_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "steps", lambda *a, **k: [
        ("x.json", ["sf", "data", "query", "--file", "q.soql", "--json"]),
        ("y.json", ["sf", "project", "deploy", "start", "--json"])])
    fake = FakeSf((0, ok_query(1), b""))
    with pytest.raises(CollectError, match="read-only guardrail"):
        collect_area("limits", "demo", tmp_path / "snap", run=fake, sleep=lambda s: None)
    assert fake.calls == [] and not (tmp_path / "snap").exists()


@pytest.mark.parametrize("alias", ["", "demo; rm -rf x", "a b", "$(whoami)"])
def test_bad_alias_is_refused(alias):
    with pytest.raises(PlanError):
        steps("limits", alias, ".")


def test_bad_object_name_is_refused():
    with pytest.raises(PlanError):
        steps("objects-config", "demo", runner.REPO, ["Case; deploy"])


def test_objects_config_collects_opportunity_stages():
    plan = dict(steps("objects-config", "demo", runner.REPO))
    args = plan["opportunity-stages.json"]
    assert args[:5] == ["sf", "data", "query", "--file", "queries/objects-config/opportunity-stages.soql"]
    assert "--use-tooling-api" not in args
    soql = (runner.REPO / "queries" / "objects-config" / "opportunity-stages.soql").read_text(encoding="utf-8")
    assert "FROM OpportunityStage" in soql and all(f in soql for f in ("IsActive", "IsClosed", "IsWon"))


def test_checks_can_read_what_collect_wrote(tmp_path):
    fake = FakeSf((0, ok_query(5), b""))
    collect_area("permissions", "demo", tmp_path / "snap", run=fake, sleep=lambda s: None)
    assert len(Snapshot(tmp_path / "snap").records("permissions", "assignments")) == 5


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner, "run_sf", FakeSf((0, ok_query(1), b"")))
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    snap = str(tmp_path / "snap")
    assert main(["area", "limits", "--alias", "demo", "--snapshot", snap]) == 0
    assert "limits: 1 ok, 0 failed" in capsys.readouterr().out
    assert main(["area", "limits", "--alias", "demo", "--snapshot", snap]) == 2      # reuse refused
    monkeypatch.setattr(runner, "run_sf", FakeSf((1, b"", b"boom")))
    assert main(["area", "automations", "--alias", "demo", "--snapshot", snap]) == 1


def test_describe_custom_adds_every_custom_object(tmp_path):
    custom = json.dumps({"status": 0, "result": {"records": [
        {"DeveloperName": "Library_Book", "NamespacePrefix": None},
        {"DeveloperName": "Widget", "NamespacePrefix": "acme"}], "done": True}}).encode()
    describe = json.dumps({"status": 0, "result": {"name": "X", "fields": []}}).encode()

    def fake(args, cwd):
        if "custom-objects.tooling.soql" in " ".join(args):
            return 0, custom, b""
        return 0, describe if "describe" in args else ok_query(1), b""
    m = collect_area("objects-config", "demo", tmp_path / "s", objects=["Case", "Library_Book__c"],
                     describe_custom=True, run=fake, sleep=lambda s: None)
    names = [f["file"] for f in m["files"]]
    assert names.count("describe-Library_Book__c.json") == 1            # no duplicate
    assert "describe-acme__Widget__c.json" in names and "describe-Case.json" in names
    assert all(f["status"] == "ok" for f in m["files"])
