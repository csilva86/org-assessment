"""What each area collects: a fixed list of read-only `sf` commands. Nothing else can run."""
import re
from pathlib import Path

AREAS = ("licenses-users", "permissions", "objects-config", "automations", "limits")
ALIAS = re.compile(r"^[A-Za-z0-9_.@-]+$")
OBJECT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class PlanError(Exception):
    pass


def steps(area, alias, repo, objects=None):
    """Return [(file_name, args)] for `area`. Every command is read-only and gets --json."""
    if area not in AREAS:
        raise PlanError(f"unknown area '{area}'; use one of {', '.join(AREAS)}")
    if not ALIAS.match(alias or ""):
        raise PlanError(f"invalid org alias '{alias}'")
    target = ["--target-org", alias, "--json"]
    out = []
    for q in sorted((Path(repo) / "queries" / area).glob("*.soql")):
        name = q.name[: -len(".soql")]
        args = ["sf", "data", "query", "--file", f"queries/{area}/{q.name}"]
        if name.endswith(".tooling"):
            name = name[: -len(".tooling")]
            args.append("--use-tooling-api")
        out.append((f"{name}.json", args + target))
    if area == "objects-config":
        out.append(("sobjects.json", ["sf", "sobject", "list", "--sobject", "all"] + target))
        for obj in objects or []:
            if not OBJECT.match(obj):
                raise PlanError(f"invalid object name '{obj}'")
            out.append((f"describe-{obj}.json", ["sf", "sobject", "describe", "--sobject", obj] + target))
    if area == "limits":
        out.append(("limits.json", ["sf", "org", "list", "limits"] + target))
    return out
