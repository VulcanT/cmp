"""Parse Apple Ads Platform API keyword list + keyword report into domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from cmp.domain import Keyword, KeywordStatus, Warning, money


@dataclass(frozen=True)
class AppleDaily:
    keyword_id: int
    day: date
    spend: Decimal
    taps: int
    impressions: int
    installs: int


def parse_ad_group_default_bids(ad_groups: list[dict[str, Any]]) -> dict[int, Decimal]:
    out: dict[int, Decimal] = {}
    for g in ad_groups:
        bid = g.get("defaultBid") or g.get("defaultCptBid") or {}
        out[int(g["id"])] = money(bid.get("amount", "0"))
    return out


def parse_keywords(
    rows: list[dict[str, Any]], default_bids: dict[int, Decimal]
) -> tuple[list[Keyword], list[Warning]]:
    keywords: list[Keyword] = []
    warnings: list[Warning] = []
    for r in rows:
        if r.get("deleted"):
            continue
        text = str(r["text"])
        if text != text.lower():
            warnings.append(
                Warning(
                    int(r["id"]),
                    "uppercase_keyword",
                    f"'{text}' has uppercase letters; AppsFlyer will not report its cost",
                )
            )
        bid = r.get("bid") or {}
        keywords.append(
            Keyword(
                keyword_id=int(r["id"]),
                ad_group_id=int(r["adGroupId"]),
                campaign_id=int(r["campaignId"]),
                text=text.lower(),
                match_type=str(r.get("matchType", "")),
                bid=money(bid.get("amount", "0")),
                currency=str(bid.get("currency", "USD")),
                status=KeywordStatus(str(r.get("status", "ENABLED"))),
                ad_group_default_bid=default_bids.get(int(r["adGroupId"]), money("0")),
            )
        )
    return keywords, warnings


def parse_keyword_report(rows: list[dict[str, Any]]) -> list[AppleDaily]:
    out: list[AppleDaily] = []
    for row in rows:
        kid = int(row["metadata"]["id"])
        for g in row.get("granularMetrics", []):
            out.append(
                AppleDaily(
                    keyword_id=kid,
                    day=date.fromisoformat(g["date"]),
                    spend=money((g.get("localSpend") or {}).get("amount", "0")),
                    taps=int(g.get("taps", 0)),
                    impressions=int(g.get("impressions", 0)),
                    installs=int(g.get("totalInstalls", g.get("tapInstalls", 0))),
                )
            )
    return out
