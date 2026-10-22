# Specs

One file per capability. Each spec has: Goal, Inputs, Behaviour, Acceptance criteria, Out of scope, Verification.
Agents implement from these; if behaviour changes, the spec changes in the same PR.

| Spec | Module | Status |
| --- | --- | --- |
| `ingest.md` | `src/cmp/ingest` | draft; aggregates, match rate and attribution added 2026-10-22 |
| `rules.md` | `src/cmp/rules` | v1 implemented (engine + guards); v2 schema, gates, run log and templates spec'd 2026-10-22 |
| `approvals.md` | `src/cmp/approvals` | draft; `changes` table, log and changes pages added 2026-10-22 |
| `executor.md` | `src/cmp/executor` | implemented (dry-run only); `changes` rows added 2026-10-22 |

Suggested build order for the v2 deltas: ingest aggregates + match rate → loader v2 + engine gates/log → templates → approvals log/changes pages → executor `changes` rows.

Workflow for a new capability: in Claude Code run
`I want to build <feature>. Interview me using AskUserQuestion, then write specs/<feature>.md`,
then start a fresh session: `Implement specs/<feature>.md. Write tests first, run make test, then ask the reviewer subagent to check the diff against the spec.`
