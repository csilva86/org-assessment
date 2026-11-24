"""Tests for the org documentation generator, on the fictional snapshot only."""
from pathlib import Path

from orgdoc.__main__ import main
from orgdoc.build import build, to_html, to_markdown

SNAP = Path(__file__).parent / "fixtures" / "snapshot-basic"


def doc():
    snap, sections = build(SNAP)
    return {s.id: s for s in sections}, to_markdown(snap, sections), to_html(snap, sections)


def test_sections_in_order():
    sections, md, _ = doc()
    assert list(sections) == ["overview", "licenses", "dictionary", "permissions", "automations", "limits", "method"]
    assert "Developer Edition" in md and "Production-type org" in md


def test_users_are_counted_never_named():
    _, md, html = doc()
    for name in ("Ana Fictícia", "Bruno Inventado", "Carla Exemplo"):
        assert name not in md and name not in html
    assert "| Support Profile | Salesforce | 2 |" in md
    assert "2 active and 1 inactive users." in md


def test_data_dictionary():
    _, md, _ = doc()
    assert "Library Book (Library_Book__c) — custom object, 5 fields" in md
    assert "| Title__c | Title | string(255) | yes |" in md
    assert "| Owner_Account__c | Owner | reference → Account |  |" in md
    assert "| Available__c | Available | double(18,0) · formula |  |" in md
    assert "Case (Case) — standard object, 3 fields; 1 custom shown" in md
    assert "Subject" not in md.split("Case (Case)")[1].split("##")[0]          # standard field not listed


def test_permission_matrix_and_admin_permissions():
    _, md, _ = doc()
    assert "| Support Agent | RCE | RCE |" in md            # Case, Library_Book__c (sorted: Case first)
    assert "| Profile: Support Profile |" in md
    assert "Customize Application" in md
    admin = md.split("### Admin-level permissions")[1]
    assert "| Profile: Support Profile |  |  | ✓ |  |  | 2 |" in admin


def test_automation_map_flags_old_apex_and_legacy():
    _, md, _ = doc()
    assert "| Case | CaseTrigger | Case_After_Save | Case_Escalation_Process | Notify_Owner |" in md
    assert "| LegacyHelper | 42.0 |" in md and "CaseService" not in md.split("below API version")[1]


def test_methodology_lists_sources_and_commands():
    _, md, _ = doc()
    appendix = md.split("## Appendix: methodology")[1]
    assert "permissions/object-permissions.json | ok | (fixture) object-permissions.json" in appendix
    assert "objects-config/describe-Library_Book__c.json" in appendix


def test_html_is_self_contained_and_escaped():
    _, _, html = doc()
    assert html.startswith("<!DOCTYPE html>") and "<script" not in html and "<link" not in html
    assert "Ana Fictícia" not in html


def test_cli_writes_into_reports(tmp_path):
    import shutil
    snap = tmp_path / "snapshots" / "fixture" / "t1"
    shutil.copytree(SNAP, snap)
    assert main(["build", str(snap)]) == 0
    out = tmp_path / "reports" / "fixture" / "t1"
    assert (out / "org-documentation.md").exists() and (out / "org-documentation.html").exists()
    assert main(["build", str(tmp_path / "nope")]) == 2


def test_users_without_profile_are_labelled(tmp_path):
    import json, shutil
    snap = tmp_path / "snap"
    shutil.copytree(SNAP, snap)
    f = snap / "licenses-users" / "users.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["result"]["records"].append({"Id": "005Z", "Name": "Automated Process", "IsActive": True, "Profile": None})
    f.write_text(json.dumps(data), encoding="utf-8")
    snap_obj, sections = build(snap)
    assert "(no profile: platform or automated user)" in to_markdown(snap_obj, sections)
