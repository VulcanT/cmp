"""Join Apple keyword data with AppsFlyer cohort rows and build KeywordWindow objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from cmp.domain import Keyword, KeywordDaily, KeywordWindow, Warning, money
from cmp.ingest.apple_reports import AppleDaily
from cmp.ingest.appsflyer import CohortRow


@dataclass
class ReconcileResult:
    daily: list[KeywordDaily] = field(default_factory=list)
    unmapped: list[tuple[str, str, str]] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)


def _period(row: CohortRow | None, p: int) -> Decimal:
    if row is None:
        return Decimal("0")
    return row.by_period.get(p, Decimal("0"))


def reconcile(
    keywords: list[Keyword],
    names: dict[int, tuple[str, str]],  # keyword_id -> (campaign name, ad group name)
    apple_daily: list[AppleDaily],
    af_revenue: list[CohortRow],
    cohort_date: date,
) -> ReconcileResult:
    """Build one KeywordDaily per keyword for `cohort_date`.

    AppsFlyer cohort rows are cumulative over the from..to range; Phase 1 calls the API per cohort
    date (from == to) so one row == one cohort day. Revenue D0/D7 come from period 0 and 7.
    """
    result = ReconcileResult()
    by_name: dict[tuple[str, str, str], Keyword] = {}
    for kw in keywords:
        c, g = names.get(kw.keyword_id, ("", ""))
        by_name[(c, g, kw.text)] = kw

    af_by_kw: dict[int, CohortRow] = {}
    for row in af_revenue:
        kw = by_name.get((row.campaign, row.adset, row.keyword))
        if kw is None:
            result.unmapped.append((row.campaign, row.adset, row.keyword))
            continue
        af_by_kw[kw.keyword_id] = row

    apple_by_kw = {a.keyword_id: a for a in apple_daily if a.day == cohort_date}
    for kw in keywords:
        a = apple_by_kw.get(kw.keyword_id)
        r = af_by_kw.get(kw.keyword_id)
        if a is None and r is None:
            continue
        d = KeywordDaily(
            keyword_id=kw.keyword_id,
            cohort_date=cohort_date,
            af_cost=r.cost if r else money("0"),
            asa_spend=a.spend if a else money("0"),
            installs=r.users if r else (a.installs if a else 0),
            revenue_d0=money(_period(r, 0)),
            revenue_d7=money(_period(r, 7)),
            taps=a.taps if a else 0,
            impressions=a.impressions if a else 0,
        )
        result.daily.append(d)
        mm = d.cost_mismatch_pct
        if mm is not None and mm > Decimal("0.05"):
            result.warnings.append(
                Warning(
                    kw.keyword_id,
                    "cost_mismatch",
                    f"af_cost {d.af_cost} vs asa_spend {d.asa_spend} ({mm:.1%})",
                )
            )
    return result


def build_windows(
    keywords: list[Keyword],
    daily: list[KeywordDaily],
    as_of: date,
    last_change: dict[int, date] | None = None,
    first_seen: dict[int, date] | None = None,
) -> list[KeywordWindow]:
    """7-day window ending at as_of (inclusive of D-1), plus 14-day spend/installs."""
    last_change = last_change or {}
    first_seen = first_seen or {}
    by_kw: dict[int, list[KeywordDaily]] = {}
    for d in daily:
        by_kw.setdefault(d.keyword_id, []).append(d)
    windows: list[KeywordWindow] = []
    for kw in keywords:
        rows = by_kw.get(kw.keyword_id, [])
        w7 = [r for r in rows if 0 < (as_of - r.cohort_date).days <= 7]
        w14 = [r for r in rows if 0 < (as_of - r.cohort_date).days <= 14]
        if not w14:
            continue
        lc = last_change.get(kw.keyword_id)
        fs = first_seen.get(kw.keyword_id, min(r.cohort_date for r in rows))
        windows.append(
            KeywordWindow(
                keyword=kw,
                days=len(w7),
                spend=money(sum((r.asa_spend for r in w7), Decimal("0"))),
                af_cost=money(sum((r.af_cost for r in w7), Decimal("0"))),
                installs=sum(r.installs for r in w7),
                revenue_d7=money(sum((r.revenue_d7 for r in w7), Decimal("0"))),
                days_active=(as_of - fs).days,
                last_change_days=(as_of - lc).days if lc else 999,
                spend_14d=money(sum((r.asa_spend for r in w14), Decimal("0"))),
                installs_14d=sum(r.installs for r in w14),
            )
        )
    return windows
