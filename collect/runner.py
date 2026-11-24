"""
Run one area's commands and write the files and the manifest.

Guardrail 1: `sf` runs here as a subprocess, outside Claude Code's hook. So every command is checked
with the hook's own function (`check_command` in .claude/hooks/guard_readonly.py) before it runs,
and refused if the hook would block it.
"""
import datetime as _dt
import importlib.util
import json
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from .plan import steps

REPO = Path(__file__).resolve().parents[1]
RETRY_WAIT_SECONDS = 5


def _load_guard():
    path = REPO / ".claude" / "hooks" / "guard_readonly.py"
    spec = importlib.util.spec_from_file_location("guard_readonly", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CollectError(Exception):
    pass


def utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_sf(args, cwd):
    """Run `sf` and return (exit code, stdout bytes, stderr bytes)."""
    exe = shutil.which(args[0]) or args[0]          # on Windows this finds sf.cmd
    p = subprocess.run([exe] + args[1:], cwd=cwd, capture_output=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


def _count(result):
    if isinstance(result, dict) and isinstance(result.get("records"), list):
        return len(result["records"])
    if isinstance(result, list):
        return len(result)
    return None


def _evaluate(stdout, stderr, code):
    """(status, records, error) for one command's output."""
    try:
        data = json.loads(stdout.decode("utf-8")) if stdout.strip() else None
    except ValueError:
        data = None
    if isinstance(data, dict) and data.get("status") == 0:
        return "ok", _count(data.get("result")), None
    if isinstance(data, dict):
        return "failed", None, str(data.get("message") or data.get("name") or "sf returned an error")
    lines = [l for l in stderr.decode("utf-8", errors="replace").splitlines() if l.strip()]
    return "failed", None, (lines[-1].strip() if lines else f"sf exited with code {code} and wrote nothing")


def _custom_object_names(folder):
    """API names of the custom objects listed in custom-objects.json (Tooling CustomObject)."""
    try:
        data = json.loads((folder / "custom-objects.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if data.get("status") != 0:
        return []
    names = []
    for rec in data["result"].get("records", []):
        ns, dev = rec.get("NamespacePrefix"), rec.get("DeveloperName")
        if dev:
            names.append(f"{ns}__{dev}__c" if ns else f"{dev}__c")
    return names


def _run_steps(plan, run, sleep, repo, folder):
    files = []
    for name, args in plan:
        attempts, ran_at = 0, None
        while True:
            attempts += 1
            ran_at = utc_now()
            code, out, err = run(args, repo)
            if code != 0 and not out.strip() and attempts == 1:
                sleep(RETRY_WAIT_SECONDS)             # one retry, same command: sf can fail once on start
                continue
            break
        (folder / name).write_bytes(out)
        (folder / (name[: -len(".json")] + ".stderr.log")).write_bytes(err)
        status, records, error = _evaluate(out, err, code)
        files.append({"file": name, "command": shlex.join(args), "ran_at": ran_at, "status": status,
                      "records": records, "attempts": attempts, "error": error})
    return files


def _refuse_unsafe(guard, plan):
    for _, args in plan:                              # refuse before running anything
        reason = guard.check_command(shlex.join(args))
        if reason:
            raise CollectError(f"refused by the read-only guardrail: {reason}")


def collect_area(area, alias, snapshot, objects=None, describe_custom=False, run=None, sleep=None, repo=REPO):
    """Collect one area. With describe_custom (objects-config only), every custom object found in
    custom-objects.json is described too, after the requested objects."""
    run = run or run_sf
    sleep = sleep or time.sleep
    snapshot = Path(snapshot)
    folder = snapshot / area
    if (folder / "_manifest.json").exists():
        raise CollectError(f"{folder} already has a manifest. Never reuse a snapshot: start a new one.")
    guard = _load_guard()
    objects = list(objects or [])
    plan = steps(area, alias, repo, objects)
    _refuse_unsafe(guard, plan)
    folder.mkdir(parents=True, exist_ok=True)
    files = _run_steps(plan, run, sleep, repo, folder)

    if area == "objects-config" and describe_custom:
        extra = [o for o in _custom_object_names(folder) if o not in objects]
        if extra:
            more = [s for s in steps(area, alias, repo, extra) if s[0].startswith("describe-")]
            _refuse_unsafe(guard, more)
            files += _run_steps(more, run, sleep, repo, folder)
        objects += extra

    if area == "objects-config" and not objects:
        files.append({"file": "describe-<Object>.json", "command": None, "ran_at": utc_now(),
                      "status": "skipped", "records": None, "attempts": 0,
                      "error": "No objects were listed: /run-assessment passes the objects named in the approved requirements."})

    manifest = {"area": area, "org_alias": alias, "snapshot": snapshot.as_posix(),
                "collected_by": "python -m collect", "files": files}
    (folder / "_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
