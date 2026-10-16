"""AppsFlyer Cohort API client. Docs: see .claude/skills/appsflyer-api/SKILL.md."""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import httpx

COHORT_URL = "https://hq1.appsflyer.com/api/cohorts/v1/data/app/{app_id}"
ASA_PID = "Apple Search Ads"


class AppsFlyerClient(Protocol):
    def cohort(self, app_id: str, start: date, end: date, kpi: str) -> dict[str, Any]: ...


def cohort_body(start: date, end: date, kpi: str) -> dict[str, Any]:
    return {
        "cohort_type": "user_acquisition",
        "aggregation_type": "cumulative",
        "from": start.isoformat(),
        "to": end.isoformat(),
        "groupings": ["c", "af_adset", "af_keywords"],
        "kpis": [kpi],
        "filters": {"pid": [ASA_PID], "period": [0, 1, 3, 7]},
        "preferred_currency": True,
        "preferred_timezone": True,
        "partial_data": False,
    }


class HttpAppsFlyerClient:
    """Real client. Paces to ≤ 50 calls/min (limit is 60)."""

    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=60)
        self._headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
        self._last_call = 0.0

    def cohort(self, app_id: str, start: date, end: date, kpi: str) -> dict[str, Any]:
        gap = 1.2 - (time.monotonic() - self._last_call)
        if gap > 0:
            time.sleep(gap)
        resp = self._client.post(
            COHORT_URL.format(app_id=app_id),
            headers=self._headers,
            json=cohort_body(start, end, kpi),
        )
        self._last_call = time.monotonic()
        if resp.status_code == 429:
            time.sleep(60)
            return self.cohort(app_id, start, end, kpi)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data


class FixtureAppsFlyerClient:
    """Reads tests/fixtures/appsflyer/<app_id>_<kpi>.json; no network."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def cohort(self, app_id: str, start: date, end: date, kpi: str) -> dict[str, Any]:
        dated = self.root / f"{app_id}_{kpi}_{start.isoformat()}.json"
        path = dated if dated.exists() else self.root / f"{app_id}_{kpi}.json"
        data: dict[str, Any] = json.loads(path.read_text())
        return data
