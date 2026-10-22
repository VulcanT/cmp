# Spec: approvals

## Goal
One page per batch date listing proposals with evidence; approve or reject individually or in bulk; every decision recorded; every change to Apple — ours or someone else's — recorded in one `changes` table; every rule evaluation inspectable.

## Behaviour
- `GET /batches/{date}`: table of proposals (app, campaign, ad group, keyword, rule, current → proposed, ROAS D7, spend, installs, match rate), with Approve / Reject buttons (htmx, no page reload) and "Approve all winners" / "Reject all". Gate holds (`cost_mismatch`, `match_rate_low`) are listed under the table with their values.
- `POST /proposals/{id}/decide` with `decision` in {approved, rejected} and optional `note`; writes `decisions` row and updates `proposals.status`.
- `POST /batches/{date}/execute`: hands all `approved` proposals to the executor; shows per-item result.
- `GET /batches/{date}/log`: the full evaluation log (`rule_evaluations`, specs/rules.md §7) with filters for keyword, rule and reason, and counts by outcome and reason at the top. This is MobileAction's "Full Logs" view: every check, including the ones that changed nothing.
- `GET /changes`: the `changes` table, newest first, filterable by app, entity, agent and rule.
- Daily digest: after ingest + rules, send an email/Slack message (transport pluggable; log-only in Phase 1) with: proposals by rule; skipped by reason; notify-only rule hits; app match rate and the 10 lowest keywords; unmapped rows; link to the batch page.

### `changes` table
| Column | Meaning |
| --- | --- |
| `id`, `ts` | row id, UTC timestamp |
| `app_id`, `entity_level`, `entity_id` | `keyword` in Phase 1; `ad_group`, `campaign` later |
| `field` | `bid` or `status` |
| `old`, `new` | values as strings (money as decimal string with currency) |
| `agent` | `rule` (an approved proposal that a rule created), `manual` (reserved: an approved proposal a person created in the UI — still a proposal, so invariant 1 holds; no UI for it in Phase 1), `external` (detected by the drift check: changed in the Apple console or elsewhere) |
| `rule_id`, `proposal_id`, `decision_id` | set when `agent = rule` (`rule_id` null for `manual`) |
| `execution_id` | FK to `executions` (the bulk-update call that applied it); null for `external` |

Writers: the executor only. Applied items → `rule` (live mode only, since dry-run applies nothing); drifted items → `external`, with `old` = `evidence_json.seen_*` and `new` = the value read back, in dry-run and live alike. Nothing deletes rows.

## Acceptance criteria
- Deciding twice on the same proposal is rejected with 409.
- Executing a batch with zero approved proposals is a no-op with a clear message.
- A fixture batch with one applied and one drifted keyword, executed in live mode with the fake client, yields exactly one `changes` row with `agent = rule` and one with `agent = external`.
- `/batches/{date}/log` filtered by `reason = insufficient_sample` lists the fixture keyword that failed its sample floor.
- Pages render with no JavaScript framework beyond htmx.

## Verification
`pytest tests/approvals -q`; manual: `make run`, open `/batches/<yesterday>`, `/batches/<yesterday>/log` and `/changes` against fixture data.
