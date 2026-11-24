# Requirements files

One YAML file per project: `requirements/<project>.yaml`. It holds the client's business
rules and, under each rule, the technical checks that prove whether the org meets it.

> Status: first draft of the format. It will change as the first checks are built.

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
        notes: ""              # assumptions, open questions
```

## Results

Every check ends as `met`, `partial` or `not_met`, with the evidence: the snapshot file and
the path inside it that proves the result (guardrail 5).
