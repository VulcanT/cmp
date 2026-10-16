# Spec: executor

## Goal
Apply approved proposals to Apple Ads with full auditability, and never anything else.

## Behaviour
1. Input: list of `Proposal` with `status=approved` for one app/ad account.
2. Re-check guardrails (`guards.py`) on the batch; drop violators with `status=failed`, reason `guard`.
3. Re-read each keyword from Apple (`POST /v1/keywords/query` by id). If `bid` or `status` differs from `evidence_json.seen_bid/seen_status`, mark `failed`, reason `drifted` (someone changed it in the console).
4. Build one `POST /v1/keywords/bulk-update` request per ad account: `items[{correlationId: proposal.id, data: {id, bid?: {amount, currency}, status?}}]`, `allowPartialSuccess: true`. Chunk at 500 items.
5. `CMP_MODE=dry_run` (default): write the request JSON to `executions` with `http_status=null` and mark proposals `dry_run`. `CMP_MODE=live`: send, store response, mark each proposal `applied` or `failed` from `result[].success`.
6. Rate limits: read `RateLimit-Remaining`; sleep `RateLimit-Reset` when < 5; on 429 wait `Retry-After`, double up to 16 s, max 5 retries.
7. Never delete keywords. Never create campaigns, ad groups or budgets.

## Acceptance criteria
- Dry-run produces byte-exact request JSON for a fixture batch (golden file test).
- A drifted keyword is skipped and reported; the rest of the batch still goes.
- `CMP_MODE` unset → dry-run; a test asserts that no HTTP client is invoked in dry-run.

## Verification
`pytest tests/executor -q`; first live run is done with one keyword, then confirmed in Apple Ads Change History.
