"""Apple Ads Platform API client (api.ads.apple.com/v1).

Thin wrapper so the rest of the code never sees HTTP. Docs: .claude/skills/apple-ads-api/SKILL.md.
The official SDK (`apple-ads-platform`) can replace HttpAppleAdsClient later; keep this interface.
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import httpx

BASE = "https://api.ads.apple.com/v1"
TOKEN_URL = "https://appleid.apple.com/auth/oauth2/token"


class AppleAdsClient(Protocol):
    def query_keywords(self, ad_account_id: int, campaign_id: int) -> list[dict[str, Any]]: ...
    def query_ad_groups(self, ad_account_id: int, campaign_id: int) -> list[dict[str, Any]]: ...
    def keyword_report(
        self, ad_account_id: int, campaign_id: int, start: date, end: date
    ) -> list[dict[str, Any]]: ...
    def bulk_update_keywords(self, ad_account_id: int, body: dict[str, Any]) -> dict[str, Any]: ...


def keyword_report_body(campaign_id: int, start: date, end: date) -> dict[str, Any]:
    return {
        "filters": [{"field": "campaignId", "operator": "EQUALS", "value": str(campaign_id)}],
        "timeRange": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timeZone": "ORTZ",
            "granularity": "DAILY",
        },
        "pagination": {"offset": 0, "pageSize": 5000},
    }


class TokenProvider(Protocol):
    def get_token(self) -> str: ...


class HttpAppleAdsClient:
    """Rate-limit aware HTTP client following Apple's documented backoff."""

    def __init__(self, tokens: TokenProvider, client: httpx.Client | None = None) -> None:
        self._tokens = tokens
        self._client = client or httpx.Client(timeout=60)

    def _request(
        self, method: str, path: str, ad_account_id: int | None, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._tokens.get_token()}"}
        if ad_account_id is not None:
            headers["X-AP-Context"] = f"adAccountId={ad_account_id}"
        wait = 2.0
        for _ in range(5):
            resp = self._client.request(method, f"{BASE}{path}", headers=headers, json=body)
            if resp.status_code == 429:
                retry = resp.headers.get("Retry-After") or resp.headers.get("RateLimit-Reset")
                time.sleep(float(retry) if retry else wait)
                wait = min(wait * 2, 16)
                continue
            remaining, reset = (
                resp.headers.get("RateLimit-Remaining"),
                resp.headers.get("RateLimit-Reset"),
            )
            if remaining is not None and reset is not None and int(remaining) < 5:
                time.sleep(int(reset))
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        raise RuntimeError("Apple Ads API: exceeded retries on 429")

    def _query_all(
        self, path: str, ad_account_id: int, filters: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset, size = 0, 500
        while True:
            body = {
                "filters": filters,
                "pagination": {"offset": offset, "pageSize": size, "fetchTotalCount": True},
            }
            data = self._request("POST", path, ad_account_id, body)
            rows.extend(data.get("result", []))
            total = int(data.get("pagination", {}).get("totalCount", len(rows)))
            offset += size
            if offset >= total:
                return rows

    def query_keywords(self, ad_account_id: int, campaign_id: int) -> list[dict[str, Any]]:
        return self._query_all(
            "/keywords/query",
            ad_account_id,
            [{"field": "campaignId", "operator": "EQUALS", "value": campaign_id}],
        )

    def query_ad_groups(self, ad_account_id: int, campaign_id: int) -> list[dict[str, Any]]:
        return self._query_all(
            "/adgroups/query",
            ad_account_id,
            [{"field": "campaignId", "operator": "EQUALS", "value": campaign_id}],
        )

    def keyword_report(
        self, ad_account_id: int, campaign_id: int, start: date, end: date
    ) -> list[dict[str, Any]]:
        data = self._request(
            "POST",
            "/reports/apps/keywords/query",
            ad_account_id,
            keyword_report_body(campaign_id, start, end),
        )
        rows: list[dict[str, Any]] = data.get("result", {}).get("rows", [])
        return rows

    def bulk_update_keywords(self, ad_account_id: int, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/keywords/bulk-update", ad_account_id, body)


class FixtureAppleAdsClient:
    """Reads tests/fixtures/apple/*.json; records bulk-update bodies instead of sending."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.sent: list[dict[str, Any]] = []

    def _load(self, name: str) -> Any:
        return json.loads((self.root / f"{name}.json").read_text())

    def query_keywords(self, ad_account_id: int, campaign_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = self._load(f"keywords_{campaign_id}")["result"]
        return rows

    def query_ad_groups(self, ad_account_id: int, campaign_id: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = self._load(f"adgroups_{campaign_id}")["result"]
        return rows

    def keyword_report(
        self, ad_account_id: int, campaign_id: int, start: date, end: date
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = self._load(f"keyword_report_{campaign_id}")["result"]["rows"]
        return rows

    def bulk_update_keywords(self, ad_account_id: int, body: dict[str, Any]) -> dict[str, Any]:
        self.sent.append(body)
        return {
            "result": [
                {"correlationId": i["correlationId"], "success": True} for i in body["items"]
            ]
        }
