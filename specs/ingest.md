# Spec: ingest

## Goal
Every morning at 10:00 Australia/Sydney, build `keyword_daily` rows for cohort dates D-1 .. D-7 for every enabled app, from AppsFlyer (ROAS, revenue, installs, cost) and Apple Ads (spend, taps, impressions, installs, current bid/status), plus the ad-group and campaign aggregates and the app-level gates the rules engine needs (specs/rules.md v2).

## Inputs
- `apps` table: `app_id`, `ad_account_id`, `currency`, `timezone`, `enabled`, and the attribution settings, fixed per app and copied into every proposal's `evidence_json`:
  - `cohort_type` (default `user_acquisition` = re-attribution excluded; `unified` = included; `retargeting` = only),
  - `time_basis` (`install_time`, the only value the Cohort API gives),
  - `touch` (`tap_through` default; sent as the Cohort API touch-type filter when the API accepts one). Ingest records what was actually applied as `touch_effective` (`tap_through` or `all`); `evidence_json.attribution` carries both.
- AppsFlyer Cohort API: `POST https://hq1.appsflyer.com/api/cohorts/v1/data/app/{app_id}`
  - body: `cohort_type=<apps.cohort_type>`, `aggregation_type=cumulative`, `from/to` = D-7..D-1,
    `groupings=["c","af_adset","af_keywords"]`, `filters={"pid":["Apple Search Ads"]}`, one call per KPI: `roas`, `revenue`.
  - Always returns `users`, `ecpi`, `cost`. Use `partial_data=false`. Period columns 0..7 → D0, D1, D3 and D7 values.
- Apple Ads Platform API:
  - `POST /v1/keywords/query` filtered by each `campaignId` to refresh `keywords` (id, text, matchType, bid, status).
  - `POST /v1/reports/apps/keywords/query` with `timeRange{start:D-7,end:D-1,timeZone:ORTZ,granularity:DAILY}` filtered by `campaignId`; rows carry `localSpend`, `impressions`, `taps`, `tapInstalls`, `totalInstalls`.
  - Impression share: **verify** whether the Platform API exposes an impression-share report; if it does, pull it weekly into `keyword_daily.impression_share`, else leave the column null.

## Behaviour
1. Pull Apple keyword list first; upsert `keywords` (lowercase `text`).
2. Pull Apple keyword report; key by `keyword_id` + `date`.
3. Pull AppsFlyer cohort rows; key by (`campaign_name`, `adset_name`, lowercase `keyword_text`) → map to `keyword_id` via `keywords` joined to campaign/ad group names. Unmapped rows go to `ingest_unmapped` with a reason.
4. Upsert `keyword_daily` for each (keyword_id, cohort_date): `af_cost`, `asa_spend`, `installs` (AppsFlyer `users`; 0 and `af_mapped = false` when the keyword has no AppsFlyer row — no fallback to Apple installs), `apple_installs` (`tapInstalls`, not `totalInstalls`), `revenue_d0`, `revenue_d1`, `revenue_d3`, `revenue_d7`, `roas_d0`, `roas_d1`, `roas_d3`, `roas_d7`, `taps`, `impressions`, `impression_share` (nullable), `cost_mismatch_pct = abs(af_cost - asa_spend) / asa_spend` (null when asa_spend = 0). The reconcile warning code is `cost_mismatch` (same code as the rules gate).
5. Build `ad_group_daily` and `campaign_daily` by summing `keyword_daily` over the same dates: Apple columns (`asa_spend`, `apple_installs`, `taps`, `impressions`) over every keyword; AppsFlyer columns (`af_cost`, `installs`, `revenue_*`) and `af_spend` (= `asa_spend` of `af_mapped` keywords only) so that `roas_* = revenue_* / af_spend` is not deflated by unmapped keywords. Ratios are recomputed from the sums, never averaged.
6. Compute match rates over the 7-day window: `keyword.match_rate_7d = installs / apple_installs` (null when `apple_installs = 0`) and `app.match_rate_7d` from the app sums; write an `ingest_warnings` row when the app rate is below `Guardrails.min_app_match_rate` (0.80, imported from `cmp.rules.guards`), listing the 10 lowest keywords with `apple_installs >= Guardrails.min_installs_for_match_rate` (5).
7. Re-pulling D-2..D-7 overwrites earlier values (late revenue and cost corrections).
8. Rate limiting: AppsFlyer ≤ 50 calls/min (headroom under 60); Apple: honour `RateLimit-Remaining`/`Retry-After`.

## Acceptance criteria
- Given recorded fixtures for one app and 7 days, `keyword_daily` has one row per keyword per date, `cost_mismatch_pct` is computed, and `campaign_daily.cpa` equals campaign spend ÷ campaign `apple_installs` (not the mean of keyword CPAs).
- Keywords with uppercase text in Apple are flagged in `ingest_warnings` (AppsFlyer will not report their cost).
- A fixture app whose AppsFlyer installs are 60% of Apple tap installs produces an `ingest_warnings` row with the lowest keywords; one at 90% produces none.
- `evidence_json.attribution` on a proposal equals the `apps` row values plus `touch_effective`.
- A keyword present in the Apple report but absent from AppsFlyer gets `installs = 0`, `af_mapped = false` and a null `match_rate_7d` contribution, never Apple installs copied into `installs`.
- A second run on the same dates is idempotent (row count unchanged, values updated).
- No network in tests.

## Out of scope
Search Match keywords (no keyword text from Apple), SKAN data, retargeting cohorts, goal-event KPIs (Phase 2 templates), search-term reports (Phase 2).

## Verification
`make daily-dry` runs ingest against `tests/fixtures/` and prints the `keyword_daily` summary plus the app match rate; `pytest tests/ingest -q` passes.
