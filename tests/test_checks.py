"""
Tests for the deterministic checks, on a fictional snapshot (tests/fixtures/snapshot-basic).
No real org data is ever used in tests (guardrail 2).
"""
import json
import shutil
from pathlib import Path

import pytest

from checks import rules
from checks.__main__ import main
from checks.requirements import RequirementsError, load
from checks.runner import run
from checks.snapshot import Snapshot, SnapshotError

FIX = Path(__file__).parent / "fixtures"
SNAP = FIX / "snapshot-basic"
REQ = FIX / "requirements-approved.yaml"


@pytest.fixture
def snap():
    return Snapshot(SNAP)


def by_id(report):
    return {r["check_id"]: r for r in report["results"]}


# ---------------------------------------------------------------- guardrail 3
def test_draft_requirements_are_refused():
    example = Path(__file__).parents[1] / "requirements" / "example-support-sla.yaml"
    with pytest.raises(RequirementsError, match="guardrail 3"):
        load(example)


def test_approved_without_name_or_date_is_refused(tmp_path):
    text = REQ.read_text(encoding="utf-8").replace("approved_by: Test Consultant", "approved_by: null")
    f = tmp_path / "req.yaml"
    f.write_text(text, encoding="utf-8")
    with pytest.raises(RequirementsError, match="approved_by"):
        load(f)


def test_code_check_without_rule_is_refused(tmp_path):
    text = REQ.read_text(encoding="utf-8").replace(
        "        rule: {type: limit_usage_below, limit: DailyApiRequests, max_percent: 70}\n", "")
    f = tmp_path / "req.yaml"
    f.write_text(text, encoding="utf-8")
    with pytest.raises(RequirementsError, match="needs a 'rule'"):
        load(f)


def test_example_requirements_are_well_formed():
    example = Path(__file__).parents[1] / "requirements" / "example-support-sla.yaml"
    data = load(example, require_approved=False)
    assert data["status"] == "draft"


# ---------------------------------------------------------------- rules
def test_objects_exist(snap):
    assert rules.rule_objects_exist(snap, ["Case", "Entitlement"])["status"] == "met"
    r = rules.rule_objects_exist(snap, ["Entitlement", "CaseMilestone"])
    assert r["status"] == "partial" and "CaseMilestone" in r["summary"]
    assert rules.rule_objects_exist(snap, ["Nope__c"])["status"] == "not_met"


def test_licenses_available(snap):
    r = rules.rule_licenses_available(snap, ["Salesforce", "Service Cloud User"], 50)
    assert r["status"] == "partial"           # 2 + 2 = 4 free, 50 needed
    assert r["summary"].startswith("4 licenses available")
    assert rules.rule_licenses_available(snap, ["Salesforce"], 2)["status"] == "met"
    assert rules.rule_licenses_available(snap, ["Salesforce Platform"], 1)["status"] == "not_met"
    assert "Not found" in rules.rule_licenses_available(snap, ["Ghost"], 1)["summary"]


def test_object_access(snap):
    r = rules.rule_object_access(snap, ["Support_Agent", "Support Profile"], "Case", ["read", "edit"])
    assert r["status"] == "partial"
    assert "Support Profile lacks edit" in r["summary"]
    assert rules.rule_object_access(snap, ["Support_Agent"], "Case", ["read", "edit"])["status"] == "met"
    assert "not found" in rules.rule_object_access(snap, ["Ghost"], "Case", ["read"])["summary"]
    with pytest.raises(ValueError):
        rules.rule_object_access(snap, ["Support_Agent"], "Case", ["fly"])


def test_system_permissions_absent(snap):
    r = rules.rule_system_permissions_absent(
        snap, ["Support_Agent", "Support Profile"], ["PermissionsModifyAllData", "PermissionsCustomizeApplication"])
    assert r["status"] == "partial"
    assert "Support Profile has PermissionsCustomizeApplication" in r["summary"]


def test_no_legacy_automation(snap):
    r = rules.rule_no_legacy_automation(snap, "Case")
    assert r["status"] == "not_met"
    assert "1 workflow rule(s) and 1 active Process Builder" in r["summary"]
    assert rules.rule_no_legacy_automation(snap, "Account")["status"] == "met"


def test_limit_usage_below(snap):
    r = rules.rule_limit_usage_below(snap, "DailyApiRequests", 70)
    assert r["status"] == "met" and "6.7%" in r["summary"]
    assert rules.rule_limit_usage_below(snap, "DataStorageMB", 70)["status"] == "not_met"   # 80% used
    assert rules.rule_limit_usage_below(snap, "Ghost", 70)["status"] == "not_met"


# ---------------------------------------------------------------- guardrail 5: evidence
def test_every_code_result_has_evidence():
    report = run(REQ, SNAP)
    for r in report["results"]:
        if r["how"] == "code":
            assert r["evidence"], f"{r['check_id']} has no evidence"
            for ev in r["evidence"]:
                assert ev["file"].endswith(".json")


# ---------------------------------------------------------------- runner
def test_runner_traces_back_to_business_rules_and_counts():
    report = run(REQ, SNAP)
    res = by_id(report)
    assert res["BR-01.1"]["status"] == "met"
    assert res["BR-01.3"]["business_rule_id"] == "BR-01"
    assert res["BR-02.4"]["status"] == "needs_judgement"
    assert report["counts"] == {"met": 2, "partial": 4, "not_met": 1, "needs_judgement": 1, "error": 0}


def test_failed_collection_gives_error_not_a_verdict(tmp_path):
    snap_dir = tmp_path / "snapshots" / "fixture" / "t1"
    shutil.copytree(SNAP, snap_dir)
    manifest = snap_dir / "limits" / "_manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["files"][0]["status"] = "failed"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    res = by_id(run(REQ, snap_dir))
    assert res["BR-02.2"]["status"] == "error"
    assert "failed" in res["BR-02.2"]["summary"]


def test_sf_error_file_gives_error(tmp_path):
    snap_dir = tmp_path / "snap"
    shutil.copytree(SNAP, snap_dir)
    (snap_dir / "objects-config" / "sobjects.json").write_text('{"status": 1, "name": "NamedOrgNotFoundError"}', encoding="utf-8")
    res = by_id(run(REQ, snap_dir))
    assert res["BR-01.1"]["status"] == "error"


def test_cli_writes_results_into_reports(tmp_path, capsys):
    snap_dir = tmp_path / "snapshots" / "fixture" / "t1"
    shutil.copytree(SNAP, snap_dir)
    assert main(["run", str(REQ), str(snap_dir)]) == 0
    out = tmp_path / "reports" / "fixture" / "t1" / "results.json"
    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8"))["counts"]["met"] == 2
    assert "2 met · 4 partial · 1 not met" in capsys.readouterr().out


def test_cli_refuses_draft(capsys):
    example = Path(__file__).parents[1] / "requirements" / "example-support-sla.yaml"
    assert main(["run", str(example), str(SNAP)]) == 2
    assert "guardrail 3" in capsys.readouterr().err


def test_missing_snapshot_folder():
    with pytest.raises(SnapshotError):
        Snapshot("does/not/exist")


# ---------------------------------------------------------------- reports
from checks import report as rep


def test_rule_level_verdicts():
    assert rep.rule_status(["met", "met"]) == "met"
    assert rep.rule_status(["met", "partial"]) == "partial"
    assert rep.rule_status(["partial", "not_met"]) == "not_met"
    assert rep.rule_status(["met", "error"]) == "error"
    assert rep.rule_status(["needs_judgement"]) == "needs_judgement"
    assert rep.rule_status(["met", "needs_judgement"]) == "met"


def test_client_summary_speaks_business_language():
    text = rep.client_summary(run(REQ, SNAP))
    assert "Support tracks cases against an SLA." in text      # the client's own words
    assert "0 of 2 business rules are met" in text
    assert "BR-01.1" not in text and "evidence" not in text.split("---")[0].lower()
    assert "Not met" in text


def test_consultant_detail_has_evidence_and_fixes():
    text = rep.consultant_detail(run(REQ, SNAP))
    assert "### ❌ BR-01.4" in text
    assert "`automations/workflow-rules.json`" in text
    assert "Migrate the workflow rules and Process Builder processes on Case to Flow" in text
    assert "Recommended: Review the evidence" in text           # judgement check


def test_gaps_lists_only_what_is_not_met():
    g = rep.gaps(run(REQ, SNAP))
    ids = [x["check_id"] for x in g["gaps"]]
    assert set(ids) == {"BR-01.2", "BR-01.3", "BR-01.4", "BR-02.1", "BR-02.3"}
    assert ids[0].startswith("BR-01")                          # high severity first
    assert all(x["recommendation"] and x["evidence"] for x in g["gaps"])
    assert g["not_assessed"] == []


def test_reports_are_reproducible(tmp_path):
    report = run(REQ, SNAP)
    a = [p.read_text(encoding="utf-8") for p in rep.write_all(report, tmp_path / "a")]
    b = [p.read_text(encoding="utf-8") for p in rep.write_all(report, tmp_path / "b")]
    assert a == b


def test_run_writes_reports_and_report_rebuilds_them(tmp_path, capsys):
    snap_dir = tmp_path / "snapshots" / "fixture" / "t1"
    shutil.copytree(SNAP, snap_dir)
    assert main(["run", str(REQ), str(snap_dir)]) == 0
    folder = tmp_path / "reports" / "fixture" / "t1"
    for name in ("results.json", "client-summary.md", "consultant-detail.md", "gaps.json"):
        assert (folder / name).exists(), name
    (folder / "client-summary.md").unlink()
    assert main(["report", str(folder / "results.json")]) == 0
    assert (folder / "client-summary.md").exists()
