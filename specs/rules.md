# Spec: rules

## Goal
Turn `keyword_daily` into `Proposal`s using declarative YAML rules, bounded by global guardrails. The engine never calls external APIs.

## Inputs
- `rules/<app_id>.yaml` (see `rules/example.yaml`): `targets` (roas_d7, cpi), `defaults` (default bid per ad group fallback), `rules[]` each with `id`, `when` (expression over a `KeywordWindow`), `action` (`bid_pct` or `status`), `guards`.
- `KeywordWindow`: 7-day and 14-day cumulative aggregates per keyword: `spend`, `installs`, `revenue_d7`, `roas_d7`, `days_active`, `last_change_days`, `current_bid`, `ad_group_default_bid`, `status`.

## Behaviour
1. Evaluate rules in file order; the first rule that fires for a keyword wins, except `cost_mismatch_hold`, which always wins and produces a warning instead of a proposal.
2. `bid_pct` actions produce `proposed = round(current_bid * (1 + pct), 2)` then clamp with guardrails.
3. Guardrails (`guards.py`), applied in the engine and again in the executor:
   - max one proposal per keyword per batch date;
   - bid change within ±25% per day;
   - bid within [0.3×, 2×] of the ad group default bid;
   - at most 10% of an ad group's active keywords paused in one batch;
   - a proposal whose clamped value equals the current value is dropped.
4. Each proposal records `evidence_json` with the window values, rule id + version, and the bid/status seen at evaluation.

## Acceptance criteria
- `tests/rules/test_engine.py` covers: winner scaled, loser trimmed, dead paused, mismatch hold, thin-data guard, clamp to caps, pause cap per ad group, idempotent no-op.

## Out of scope
LLM-generated rules, search-term mining, negative keyword proposals (Phase 2).

## Verification
`pytest tests/rules -q` green; `make daily-dry` prints proposals for the fixture app.
