"""
Guardrail 2 for the second brain: a pattern carries no client data.

`scan(data, terms)` returns findings for a pattern:
- "block": something that is client data for sure (a record id, an email, an org URL, a custom API
  name, or a name found in this machine's snapshots or requirements files). Approval is refused.
- "warn": something the consultant must look at (a number in the text). Shown before approval.

`sensitive_terms(repo)` reads the names that identify a client from the local `snapshots/` and
`requirements/` folders: org name, aliases, user names, role names, custom objects and their
labels, project names and the permission sets the requirements name. These folders never leave
this machine, so the scan works offline and nothing is sent anywhere.
"""
import json
import re
from pathlib import Path

import yaml

# Fields written by the approval itself, not by whoever drafts the pattern.
NOT_SCANNED = {"status", "proposed_on", "approved_by", "approved_on", "seen_in_projects"}

SALESFORCE_ID = re.compile(r"\b[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ORG_URL = re.compile(r"[\w.-]+\.(?:my\.salesforce\.com|lightning\.force\.com|force\.com|my\.site\.com|"
                     r"salesforce-sites\.com|sandbox\.my\.salesforce\.com)", re.IGNORECASE)
CUSTOM_API = re.compile(r"\b\w+__(?:c|mdt|e|x|b|r|kav|share|history)\b", re.IGNORECASE)
PLACEHOLDER_SPAN = re.compile(r"<[a-z][a-z0-9_]*>")
NUMBER = re.compile(r"(?<![\w.])\d{2,}(?:[.,]\d+)?(?![\w])")
MIN_TERM = 4  # shorter names (CEO, Log) are too common to tell a client apart

# Users that every org has: their names say nothing about the client.
SYSTEM_USER_TYPES = {"AutomatedProcess", "CloudIntegrationUser", "CsnOnly", "Guest", "LicenseManager", "SelfService"}
# Standard profile names a requirements file may use: they are Salesforce's, not the client's.
STANDARD_NAMES = {"system administrator", "standard user", "standard platform user", "read only",
                  "minimum access - salesforce", "solution manager", "marketing user", "contract manager"}


def _looks_like_id(word):
    digits = sum(c.isdigit() for c in word)
    return digits >= 3 and any(c.isalpha() for c in word)


def _strings(value, path=""):
    """Yield (field path, text) for every string in a pattern, skipping approval fields."""
    if isinstance(value, dict):
        for k, v in value.items():
            if path == "" and k in NOT_SCANNED:
                continue
            yield from _strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(value, str):
        yield path, value


def scan(data, terms=()):
    findings = []
    lowered = [(t, t.lower()) for t in terms]
    for field, text in _strings(data):
        outside = PLACEHOLDER_SPAN.sub(" ", text)  # <custom_object> is fine, Pedido__c is not
        for word in SALESFORCE_ID.findall(outside):
            if _looks_like_id(word):
                findings.append(("block", field, f"looks like a Salesforce record id: {word}"))
        for m in EMAIL.findall(outside):
            findings.append(("block", field, f"email address: {m}"))
        for m in ORG_URL.findall(outside):
            findings.append(("block", field, f"org address: {m}"))
        for m in CUSTOM_API.findall(outside):
            findings.append(("block", field, f"custom API name: {m}. Write a placeholder such as <custom_object>."))
        low = outside.lower()
        for term, term_low in lowered:
            if term_low in low:
                findings.append(("block", field, f"'{term}' is a name from this machine's snapshots or requirements"))
        for m in NUMBER.findall(outside):
            findings.append(("warn", field, f"number {m}: make sure it is general knowledge, not a client figure"))
    return findings


def _records(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or data.get("status") != 0:
        return []
    result = data.get("result")
    return result.get("records", []) if isinstance(result, dict) else []


def _describe_labels(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        result = data["result"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return [result.get("label"), result.get("labelPlural")] if result.get("custom") else []


def _rule_strings(rule, key):
    value = (rule or {}).get(key)
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return [value] if isinstance(value, str) else []


def sensitive_terms(repo):
    repo = Path(repo)
    terms = set()
    snapshots = repo / "snapshots"
    if snapshots.is_dir():
        for alias in snapshots.iterdir():
            if not alias.is_dir():
                continue
            terms.add(alias.name)
            for org in alias.glob("*/objects-config/organization.json"):
                terms.update(r.get("Name") for r in _records(org))
            for users in alias.glob("*/licenses-users/users.json"):
                for r in _records(users):
                    if r.get("UserType") in SYSTEM_USER_TYPES:
                        continue
                    terms.add(r.get("Name"))
                    terms.add((r.get("UserRole") or {}).get("Name"))
            for objs in alias.glob("*/objects-config/custom-objects.json"):
                terms.update(r.get("DeveloperName") for r in _records(objs))
            for describe in alias.glob("*/objects-config/describe-*__c.json"):
                terms.update(_describe_labels(describe))
    requirements = repo / "requirements"
    if requirements.is_dir():
        for path in requirements.glob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(data, dict):
                continue
            terms.add(data.get("project"))
            for rule in data.get("rules") or []:
                for check in (rule or {}).get("checks") or []:
                    terms.update(_rule_strings(check.get("rule"), "permission_sets"))
    return sorted({t.strip() for t in terms
                   if isinstance(t, str) and len(t.strip()) >= MIN_TERM and t.strip().lower() not in STANDARD_NAMES})
