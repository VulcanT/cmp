# Specs

One file per capability. Each spec has: Goal, Inputs, Behaviour, Acceptance criteria, Out of scope, Verification.
Agents implement from these; if behaviour changes, the spec changes in the same PR.

| Spec | Module | Status |
| --- | --- | --- |
| `ingest.md` | `src/cmp/ingest` | draft |
| `rules.md` | `src/cmp/rules` | implemented (engine + guards) |
| `approvals.md` | `src/cmp/approvals` | draft |
| `executor.md` | `src/cmp/executor` | implemented (dry-run only) |

Workflow for a new capability: in Claude Code run
`I want to build <feature>. Interview me using AskUserQuestion, then write specs/<feature>.md`,
then start a fresh session: `Implement specs/<feature>.md. Write tests first, run make test, then ask the reviewer subagent to check the diff against the spec.`
