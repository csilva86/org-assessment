# Org Assessment for Salesforce

**Does this Salesforce org meet what the business asked for?** This project answers that
question automatically, with evidence, and documents the org along the way — without ever
changing it.

A consultant turns the client's business rules into technical checks. Claude Code subagents
then read the org **in parallel**, save a snapshot, and deterministic checks compare the
snapshot with the requirements. The output is a report in business language for the client,
a technical report for the consultant, and a list of gaps that a development pipeline can
pick up next.

Part of the [CSLLABS](https://csllabs.com) portfolio · Salesforce × Claude Code line.

> **Status: early stage.** Guardrails, parallel collection and deterministic checks work end to
> end on a Developer Edition org. Reports and org documentation are next (see [Roadmap](#roadmap)).

## Guardrails

These five rules shape every part of the project. The first one is enforced by code, not by
asking the model nicely.

| # | Guardrail | How it is enforced |
| --- | --- | --- |
| 1 | **Read-only.** The assessment never changes the org. | A `PreToolUse` hook ([`guard_readonly.py`](.claude/hooks/guard_readonly.py)) allows only an allowlist of read-only `sf` commands and blocks everything else, including chained commands, the legacy `sfdx` CLI, HTTP writes, write-like MCP tools and commands that print credentials. It fails closed. 62 tests cover it. |
| 2 | **Confidentiality between clients.** | `snapshots/` and `reports/` are git-ignored. The second brain stores patterns, never client data. |
| 3 | **The consultant approves.** | Agents draft checks; nothing runs until the requirements file says `status: approved`. |
| 4 | **Code before AI.** | Every check that can be exact is Python code with a reproducible result. AI is used only for judgement calls, and those are labelled. |
| 5 | **Every conclusion has evidence.** | Each result points to the snapshot file and path that proves it. |

## Guardrails in action

Things that happened while building and testing this project on a real org:

- **The consultant approves (3).** After the first run, two checks were changed to require a
  librarian permission set instead of the Standard User profile, and the file was re-approved.
  A comment left above the approval still said the file was "back to draft". On the next
  `/run-assessment`, Claude stopped at step 1: it would not treat an approval that contradicted
  the file as approval of the changed checks, and it would not change the status itself. It
  asked the consultant to either confirm the new version or set it back to draft.
- **Credentials stay out of the transcript (2).** The first end-to-end run confirmed the org with
  `sf org display --json`, which printed the session's access token. Claude flagged it without
  repeating it. The token was revoked, `/run-assessment` now confirms the org by querying the
  `Organization` record, and the hook blocks `sf org display` and `sf org list auth`.
- **The alias comes from the consultant.** When a run used an alias that did not exist on the
  machine, the CLI suggested another one. None of the five collectors used it: they stopped and
  asked.
- **Read-only, enforced by code (1).** A blocked command is never retried another way. When the
  hook wrongly blocked `sf --version 2>&1`, the agent stopped and reported it; the hook was fixed
  (redirections are now ignored) and the case became a test.

## How it works

```mermaid
flowchart LR
    BR["Business rules<br/>(client)"] --> T["requirements-translator<br/>drafts checks"]
    T --> A{"Consultant<br/>approves"}
    A --> S["/run-assessment"]
    S --> C1["licenses & users"]
    S --> C2["permissions"]
    S --> C3["objects & config"]
    S --> C4["automations"]
    S --> C5["limits"]
    C1 & C2 & C3 & C4 & C5 --> SNAP[("Snapshot<br/>JSON")]
    SNAP --> CHK["Deterministic checks"]
    CHK --> R1["Client summary"]
    CHK --> R2["Consultant detail"]
    CHK --> R3["gaps.json"]
    SNAP --> DOC["Org documentation"]
```

1. **Requirements** — business rules and their checks in a YAML file
   ([format](requirements/README.md), [example](requirements/example-support-sla.yaml)).
   Every check keeps the id of the rule it came from, so the report can say *"your SLA rule is
   not met because Entitlements are off"* instead of a loose technical list.
2. **Collection** — five subagents, one per area, run the read-only `sf` commands and the
   versioned [SOQL files](queries) in parallel, and save the raw JSON into a timestamped snapshot. Analysis never touches the live org, so
   results are reproducible and before/after runs can be compared.
3. **Analysis** — Python checks read the snapshot and return `met`, `partial` or `not_met`,
   with severity and evidence (`python -m checks run <requirements> <snapshot>`).
4. **Output** — a client summary, a consultant report and `gaps.json`.
5. **Org documentation** — data dictionary, permission matrix, automation map, licenses and
   limits, plus a methodology appendix, built from the same snapshot.
6. **Second brain** — anonymised patterns from past projects that make the next translation of
   business rules faster.

## What is in this repository

| Path | What it is |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | Instructions Claude Code reads in every session: guardrails, run order, conventions |
| [`.claude/settings.json`](.claude/settings.json) | The read-only hook and a deny list for write commands |
| [`.claude/hooks/guard_readonly.py`](.claude/hooks/guard_readonly.py) | Guardrail 1, in code |
| [`.claude/agents/`](.claude/agents) | Five collector subagents and the requirements translator |
| [`.claude/skills/`](.claude/skills) | `run-assessment` (the `/run-assessment` command) and the read-only collection reference |
| [`queries/`](queries) | The SOQL the collectors run, one query per file |
| [`requirements/`](requirements) | Requirements format, a fictional example and the demo for the author's DigiLibrary org |
| [`checks/`](checks) | Deterministic checks: six rule types, evidence for every result |
| [`brain/`](brain) | The second brain: patterns only |
| [`tests/`](tests) | Guardrail and checks tests, on fictional data only |

## Getting started

Requirements: [Salesforce CLI](https://developer.salesforce.com/tools/salesforcecli) (`sf`),
[Claude Code](https://code.claude.com), Python 3.10+, and a Salesforce org you are allowed to
read (a free Developer Edition org works).

```bash
# 1. Install the test dependencies and check the guardrail
python -m pip install -r requirements-dev.txt
python -m pytest tests

# 2. Connect the org you will assess, with an alias
sf org login web --alias demo

# 3. Open Claude Code in this folder
claude
```

In Claude Code:

1. Ask the `requirements-translator` agent to draft checks for your rules, review them, and set
   `status: approved`.
2. Run `/run-assessment requirements/<your-file>.yaml demo`.

> The hook is started with `python`. If your system only has `python3`, change `command` in
> `.claude/settings.json`.

## Roadmap

- [x] Guardrails, read-only hook and its tests (including credential-printing commands)
- [x] Collector subagents, the read-only command reference and the SOQL files
- [x] One manifest format shared by all collectors
- [x] Requirements format with rule types, a fictional example and the DigiLibrary demo
- [x] Deterministic checks: six rule types, `python -m checks run`, `results.json` with evidence
- [x] End-to-end run with `/run-assessment` on the author's DigiLibrary org
      ([requirements](requirements/demo-digilibrary.yaml)): 21 of 21 commands `ok`;
      6 met, 1 partial, 2 not met, 1 for judgement
- [x] Before/after: the two gaps (only System Administrator could use DigiLibrary) closed with a
      `DigiLibrary_Librarian` permission set; both checks went from not met to met
- [ ] Manifests written by a script, not by the agents (agents wrote local time marked as UTC, and one
      collector started before its folder existed; both worked around for now in the agents)
- [ ] Reports: client summary, consultant detail, `gaps.json`
- [ ] Org documentation generator
- [ ] Second brain: pattern format and approval flow
- [ ] Later: hand `gaps.json` to an orchestrated development pipeline and re-run the assessment
      to prove the gaps are closed

## Author

Carlos Silva — Salesforce developer (Platform Developer I, Data Cloud Specialist, AI Specialist).
[csllabs.com](https://csllabs.com) · [GitHub](https://github.com/csilva86)

## License

[MIT](LICENSE)
