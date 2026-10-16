---
name: appsflyer-api
description: AppsFlyer Cohort API and Master API cheat-sheet for Apple Search Ads keyword-level ROAS, cost and revenue. Use when touching src/cmp/clients/appsflyer_client.py or ingest/appsflyer.py.
---
# AppsFlyer aggregate APIs

Auth: `Authorization: Bearer <API V2 token>` (admin generates in dashboard; tokens issued before 2026-03-10 were revoked).
Dates `yyyy-mm-dd`; range 1–31 days. Media source for ASA: `pid = "Apple Search Ads"`.

## Cohort API (primary: has `roas`)
`POST https://hq1.appsflyer.com/api/cohorts/v1/data/app/{app_id}`
```json
{"cohort_type":"user_acquisition","aggregation_type":"cumulative",
 "from":"2026-10-07","to":"2026-10-13",
 "groupings":["c","af_adset","af_keywords"],
 "kpis":["roas"],
 "filters":{"pid":["Apple Search Ads"],"period":[0,1,3,7]},
 "preferred_currency":true,"preferred_timezone":true,"partial_data":false}
```
- Always returns `users`, `ecpi`, `cost`; exactly ONE extra KPI per call (`roas`, `revenue`, `roi`, `sessions`, `uninstalls`, or an `event_name`). Two calls per app per day: `roas` and `revenue`.
- Groupings 1–7; keyword grouping is `af_keywords`. Cost per keyword is NOT reported for keywords containing uppercase letters.
- Limits: 60 calls/min, 50,000/day, 30,000 rows per query. Cost and uninstall KPIs update daily.
- Response CSV (default) or JSON; period columns `0..N` are cohort days.
Docs: https://support.appsflyer.com/hc/en-us/articles/360004799057-Cohort-API

## Master API (cross-check: cost, installs, revenue; no roas KPI)
`GET https://hq1.appsflyer.com/api/master-agg-data/v4/app/{app_id}?from=..&to=..&groupings=pid,c,af_adset,af_keywords&kpis=installs,cost,revenue,roi,average_ecpi&pid=Apple Search Ads&format=json`
- Daily granularity, data ready 24–48 h after the day, 200K rows max.
Docs: https://support.appsflyer.com/hc/en-us/articles/213223166

## Apple Search Ads integration facts
- Keyword cost requires ROI360 and the Cost toggle on for the app; cost granularity: campaign, ad group, geo, keyword (keyword cost dims limited to date/campaign/adset — do not group keyword cost by geo).
- Keyword data lags 8–12 h; sometimes only keyword ID arrives. Re-pull D-2..D-7 daily.
- Search Match keywords are never shared; only exact/broad keywords have ROAS.
- `keyword_id` is only in raw-data exports (Pull API `additional_fields=keyword_id`), not in aggregate APIs → join on (campaign name, adset name, lowercase keyword text).
Docs: https://support.appsflyer.com/hc/en-us/articles/213747963-Apple-Search-Ads-guide
