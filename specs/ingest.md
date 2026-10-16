# Spec: ingest

## Goal
Every morning at 10:00 Australia/Sydney, build `keyword_daily` rows for cohort dates D-1 .. D-7 for every enabled app, from AppsFlyer (ROAS, revenue, installs, cost) and Apple Ads (spend, taps, impressions, current bid/status).

## Inputs
- `apps` table: `app_id`, `ad_account_id`, `currency`, `timezone`, `enabled`.
- AppsFlyer Cohort API: `POST https://hq1.appsflyer.com/api/cohorts/v1/data/app/{app_id}`
  - body: `cohort_type=user_acquisition`, `aggregation_type=cumulative`, `from/to` = D-7..D-1,
    `groupings=["c","af_adset","af_keywords"]`, `filters={"pid":["Apple Search Ads"]}`, one call per KPI: `roas`, `revenue`.
  - Always returns `users`, `ecpi`, `cost`. Use `partial_data=false`. Period columns 0..7 → D0 and D7 values.
- Apple Ads Platform API:
  - `POST /v1/keywords/query` filtered by each `campaignId` to refresh `keywords` (id, text, matchType, bid, status).
  - `POST /v1/reports/apps/keywords/query` with `timeRange{start:D-7,end:D-1,timeZone:ORTZ,granularity:DAILY}` filtered by `campaignId`.

## Behaviour
1. Pull Apple keyword list first; upsert `keywords` (lowercase `text`).
2. Pull Apple keyword report; key by `keyword_id` + `date`.
3. Pull AppsFlyer cohort rows; key by (`campaign_name`, `adset_name`, lowercase `keyword_text`) → map to `keyword_id` via `keywords` joined to campaign/ad group names. Unmapped rows go to `ingest_unmapped` with a reason.
4. Upsert `keyword_daily` for each (keyword_id, cohort_date): `af_cost`, `asa_spend`, `installs`, `revenue_d0`, `revenue_d7`, `roas_d0`, `roas_d7`, `taps`, `impressions`, `cost_mismatch_pct = abs(af_cost - asa_spend) / asa_spend` (null when asa_spend = 0).
5. Re-pulling D-2..D-7 overwrites earlier values (late revenue and cost corrections).
6. Rate limiting: AppsFlyer ≤ 50 calls/min (headroom under 60); Apple: honour `RateLimit-Remaining`/`Retry-After`.

## Acceptance criteria
- Given recorded fixtures for one app and 7 days, `keyword_daily` has one row per keyword per date, and `cost_mismatch_pct` is computed.
- Keywords with uppercase text in Apple are flagged in `ingest_warnings` (AppsFlyer will not report their cost).
- A second run on the same dates is idempotent (row count unchanged, values updated).
- No network in tests.

## Out of scope
Search Match keywords (no keyword text from Apple), SKAN data, retargeting cohorts.

## Verification
`make daily-dry` runs ingest against `tests/fixtures/` and prints the `keyword_daily` summary; `pytest tests/ingest -q` passes.
