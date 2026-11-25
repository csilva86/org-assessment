# Requirements files

One YAML file per project: `requirements/<project>.yaml`. It holds the client's business
rules and, under each rule, the technical checks that prove whether the org meets it.

> Status: v1. Seven rule types; more are added as projects need them.

## Who writes what

| Part | Written by |
| --- | --- |
| `business_rule`, `source` | The consultant, from what the client said |
| `checks` | Drafted by the `requirements-translator` agent, reviewed by the consultant |
| `status: approved`, `approved_by`, `approved_on` | **Only the consultant** (guardrail 3) |

No check runs while `status` is `draft`.

## Format

```yaml
project: <short-name>          # no client names in files you might commit or share
status: draft                  # draft | approved
approved_by: null              # consultant's name, set on approval
approved_on: null              # YYYY-MM-DD

rules:
  - id: BR-01                  # stable id: the report traces every gap back to it
    business_rule: "<what the client needs, in their words>"
    source: "<where it came from: meeting, document, email>"
    checks:
      - id: BR-01.1
        area: licenses-users   # licenses-users | permissions | objects-config | automations | limits
        what: "<what is verified, in plain words>"
        how: code              # code (exact, reproducible) | judgement (needs a person-like assessment)
        severity: high         # high | medium | low
        rule: {type: objects_exist, objects: [Case]}   # required when how: code (see below)
        notes: ""              # assumptions, open questions
```

## Rule types (`how: code`)

Each rule reads only the snapshot (`checks/rules.py`). Names are API names unless said otherwise.

| `type` | Parameters | Met when |
| --- | --- | --- |
| `objects_exist` | `objects: [Case, Library_Book__c]` | every object exists |
| `picklist_values` | `object: Opportunity`, `field: StageName`, `values: [Prospecting, Closed Won]`, optional `match: exact` (default; no other active values) or `includes`, `compare: value` (default; API value) or `label`, `ordered: false` | the active values in `describe-<object>.json` are `values`. Needs the object in `--objects` when objects-config is collected |
| `licenses_available` | `licenses: [Salesforce, Service Cloud User]` (user license names or permission set license labels), `min_available: 50` | unused licenses (total minus used), summed, reach `min_available` |
| `object_access` | `permission_sets: [Support_Agent, Standard User]` (permission set API name or label, or profile name), `object: Case`, `access: [read, create, edit, delete, view_all, modify_all]` | every permission set grants every access |
| `system_permissions_absent` | `permission_sets: [...]`, `permissions: [PermissionsModifyAllData, PermissionsCustomizeApplication]` | none of them has any of those permissions |
| `no_legacy_automation` | `object: Case`, optional `object_label: Case` | no workflow rule and no active Process Builder process on the object |
| `limit_usage_below` | `limit: DailyApiRequests`, `max_percent: 70` | usage is below the threshold |

`partial` means some, not all, of the items passed. A missing or failed snapshot file gives
`error`, never a verdict. `how: judgement` checks are listed as `needs_judgement` for the consultant.

## Running

```bash
python -m checks run requirements/<project>.yaml snapshots/<alias>/<timestamp>
```

Results go to `reports/<alias>/<timestamp>/results.json` (git-ignored).

## Results

Every check ends as `met`, `partial` or `not_met`, with the evidence: the snapshot file and
the path inside it that proves the result (guardrail 5).
