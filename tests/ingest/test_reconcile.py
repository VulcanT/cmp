from __future__ import annotations

from datetime import date
from decimal import Decimal

from cmp.ingest.apple_reports import AppleDaily, parse_keywords
from cmp.ingest.appsflyer import CohortRow, parse_cohort
from cmp.ingest.reconcile import build_windows, reconcile
from tests.conftest import make_keyword


def test_uppercase_keyword_is_warned_and_lowercased():
    kws, warns = parse_keywords(
        [
            {
                "id": 1,
                "adGroupId": 10,
                "campaignId": 100,
                "text": "Photo Editor",
                "matchType": "EXACT",
                "bid": {"amount": "1.00", "currency": "USD"},
                "status": "ENABLED",
            }
        ],
        {10: Decimal("1.00")},
    )
    assert kws[0].text == "photo editor" and warns[0].code == "uppercase_keyword"


def test_reconcile_joins_on_names_and_flags_mismatch():
    kw = make_keyword(1)
    names = {1: ("Camp", "AG")}
    d = date(2026, 10, 10)
    apple = [AppleDaily(1, d, Decimal("2.00"), 10, 100, 4)]
    af = [
        CohortRow(
            "Camp", "AG", "kw1", 4, Decimal("2.00"), "revenue", {0: Decimal("3"), 7: Decimal("9")}
        ),
        CohortRow("Camp", "AG", "unknown kw", 1, Decimal("1"), "revenue", {}),
    ]
    res = reconcile([kw], names, apple, af, d)
    assert len(res.daily) == 1 and res.daily[0].revenue_d7 == Decimal("9.00")
    assert res.daily[0].roas_d7 == Decimal("4.5000")
    assert res.unmapped == [("Camp", "AG", "unknown kw")] and res.warnings == []


def test_reconcile_warns_when_apple_and_af_cost_disagree():
    kw = make_keyword(1)
    d = date(2026, 10, 10)
    res = reconcile(
        [kw],
        {1: ("C", "G")},
        [AppleDaily(1, d, Decimal("2.00"), 1, 1, 1)],
        [CohortRow("C", "G", "kw1", 1, Decimal("1.00"), "revenue", {})],
        d,
    )
    assert [w.code for w in res.warnings] == ["cost_mismatch"]


def test_build_windows_7_and_14_day_sums():
    kw = make_keyword(1)
    d = date(2026, 10, 15)
    rows = reconcile([kw], {1: ("C", "G")}, [], [], d).daily  # empty
    assert rows == []
    from cmp.domain import KeywordDaily

    daily = [
        KeywordDaily(
            1,
            d - __import__("datetime").timedelta(days=i),
            Decimal("1"),
            Decimal("1"),
            1,
            Decimal("0"),
            Decimal("2"),
            1,
            1,
        )
        for i in range(1, 15)
    ]
    w = build_windows([kw], daily, d)[0]
    assert w.spend == Decimal("7.00") and w.spend_14d == Decimal("14.00") and w.installs_14d == 14
    assert w.roas_d7 == Decimal("2.0000") and w.days_active == 14


def test_parse_cohort_lowercases_keywords():
    rows = parse_cohort(
        {
            "results": [
                {
                    "c": "C",
                    "af_adset": "G",
                    "af_keywords": "Photo",
                    "users": 2,
                    "cost": "1.5",
                    "revenue": {"0": "1", "7": None},
                }
            ]
        },
        "revenue",
    )
    assert rows[0].keyword == "photo" and rows[0].by_period == {0: Decimal("1")}
