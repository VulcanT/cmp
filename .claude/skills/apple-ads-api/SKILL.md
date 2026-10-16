---
name: apple-ads-api
description: Apple Ads Platform API cheat-sheet (api.ads.apple.com/v1) — auth, headers, keyword endpoints, bulk updates, keyword reports, rate limits. Use when touching src/cmp/clients/apple_ads_client.py, ingest/apple_reports.py or the executor.
---
# Apple Ads Platform API (NOT Campaign Management API v5 — that one is sunset 2027-01-26)

Base: `https://api.ads.apple.com/v1`
Headers on every ad-account call: `Authorization: Bearer <token>` and `X-AP-Context: adAccountId=<id>`
Docs: https://developer.apple.com/documentation/apple-ads-platform-api (append `.md` to any page URL for plain text)

## Auth
- EC P-256 key pair; public key uploaded in Apple Ads > Account Settings > API → gives `clientId`, `teamId`, `keyId`.
- Client secret = ES256 JWT: `iss`=teamId, `sub`=clientId, `aud`=`https://appleid.apple.com`, `exp` ≤ 180 days.
- Token: `POST https://appleid.apple.com/auth/oauth2/token` form `grant_type=client_credentials&client_id=..&client_secret=<jwt>&scope=searchadsorg` → `expires_in: 3600`.
- `GET /v1/acls` (no X-AP-Context) lists ad accounts → `adAccountId`.
- Official client: `pip install apple-ads-platform` (Python 3.12+). `AppleAdsClientBuilder.from_private_key_path(client_id, team_id, key_id, path).build()`; pass `x_ap_context=f"adAccountId={id};"`.

## Query pattern (all entities)
`POST /v1/<entity>/query` with `{"filters":[{"field":"adGroupId","operator":"EQUALS","value":123}],"sorting":[...],"pagination":{"offset":0,"pageSize":500}}`. Response: `{"result":[...],"pagination":{"totalCount":..}}`.

## Keywords
- `PUT /v1/keywords/{id}` body accepts ONLY `bid: {"amount":"3.75","currency":"USD"}` and/or `status: ENABLED|PAUSED`. Amount is a string. Null bid → error. Deleted keyword → 404.
- Bulk: `POST /v1/keywords/bulk-update` `{"allowPartialSuccess":true,"items":[{"correlationId":<int>,"data":{"id":..,"bid":{..},"status":..}}]}` → `result[]` keyed by `correlationId` with `success` and per-item error. One bulk call = one rate-limit unit. Bulk delete not available yet.
- Negative keywords: `/v1/negative-keywords/bulk-create|bulk-update`.

## Keyword report
`POST /v1/reports/apps/keywords/query`
```json
{"filters":[{"field":"campaignId","operator":"EQUALS","value":"444"}],
 "timeRange":{"start":"2026-10-01","end":"2026-10-07","timeZone":"ORTZ","granularity":"DAILY"},
 "pagination":{"offset":0,"pageSize":5000}}
```
Rows: `metadata{id,text,matchType,campaignId,adGroupId,status}`, `totalMetrics`, `granularMetrics[{date,localSpend{amount,currency},impressions,taps,tapInstalls,totalInstalls}]`, optional `insights.bidRecommendation`.
Granularity: DAILY ≤ 90 days; omit `granularity` for a single day. Always filter by campaignId/adGroupId.

## Rate limits
Headers `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` (seconds) on every response; `429` adds `Retry-After`. Pace: if Remaining < 5 sleep Reset; on 429 sleep Retry-After, double to max 16 s, reset on success.

## Errors
400 bad_request, 401 unauthorized (token expired → refresh), 403 forbidden (role), 404, 429, 500. Body `{"error":{"code","message","details":[{"code","message","info"}]}}`.
