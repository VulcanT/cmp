"""Parse AppsFlyer Cohort API responses into per-(campaign, adset, keyword) rows.

NOTE: the JSON shape below is what the fixtures use. The first live task is to capture one
real Cohort API response into tests/fixtures/appsflyer/ and adjust `parse_cohort` to it.
Cohort responses carry one KPI per call plus users/ecpi/cost; period columns are cohort days.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from cmp.domain import money


@dataclass(frozen=True)
class CohortRow:
    campaign: str
    adset: str
    keyword: str  # lowercase
    users: int
    cost: Decimal
    kpi: str
    by_period: dict[int, Decimal]  # {0: ..., 1: ..., 7: ...}


def parse_cohort(payload: dict[str, Any], kpi: str) -> list[CohortRow]:
    rows: list[CohortRow] = []
    for r in payload.get("results", []):
        periods = {int(k): Decimal(str(v)) for k, v in (r.get(kpi) or {}).items() if v is not None}
        rows.append(
            CohortRow(
                campaign=str(r.get("c", "")),
                adset=str(r.get("af_adset", "")),
                keyword=str(r.get("af_keywords", "")).lower(),
                users=int(r.get("users", 0)),
                cost=money(r.get("cost", "0")),
                kpi=kpi,
                by_period=periods,
            )
        )
    return rows


def key(row: CohortRow) -> tuple[str, str, str]:
    return (row.campaign, row.adset, row.keyword)
