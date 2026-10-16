# Spec: approvals

## Goal
One page per batch date listing proposals with evidence; approve or reject individually or in bulk; every decision recorded.

## Behaviour
- `GET /batches/{date}`: table of proposals (app, campaign, ad group, keyword, rule, current → proposed, ROAS D7, spend, installs), with Approve / Reject buttons (htmx, no page reload) and "Approve all winners" / "Reject all".
- `POST /proposals/{id}/decide` with `decision` in {approved, rejected} and optional `note`; writes `decisions` row and updates `proposals.status`.
- `POST /batches/{date}/execute`: hands all `approved` proposals to the executor; shows per-item result.
- Daily digest: after ingest + rules, send an email/Slack message with counts and a link to the batch page (transport pluggable; log-only in Phase 1).

## Acceptance criteria
- Deciding twice on the same proposal is rejected with 409.
- Executing a batch with zero approved proposals is a no-op with a clear message.
- Pages render with no JavaScript framework beyond htmx.

## Verification
`pytest tests/approvals -q`; manual: `make run`, open `/batches/<yesterday>` against fixture data.
