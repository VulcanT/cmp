"""End-to-end over recorded fixtures: six keywords, every rule path, no network."""

from __future__ import annotations

from datetime import date

from cmp.clients.apple_ads_client import FixtureAppleAdsClient
from cmp.clients.appsflyer_client import FixtureAppsFlyerClient
from cmp.pipeline import fixture_app, run_app


def test_fixture_app_produces_expected_proposals(fixtures):
    res = run_app(
        fixture_app(),
        date(2026, 10, 15),
        FixtureAppsFlyerClient(fixtures / "appsflyer"),
        FixtureAppleAdsClient(fixtures / "apple"),
    )
    got = sorted((p.rule_id, p.keyword_id, p.proposed) for p in res.proposals)
    assert got == [
        ("pause_dead", 1003, "PAUSED"),
        ("scale_winner", 1001, "1.15"),
        ("trim_loser", 1002, "0.80"),
    ]
    assert [(p.keyword_id, p.reason) for p in res.dropped] == [(1005, "guard:no_op_after_clamp")]
    assert {w.code for w in res.warnings} == {
        "uppercase_keyword",
        "cost_mismatch",
        "cost_mismatch_hold",
    }
    assert len(res.daily) == 6 * 14 and res.unmapped == []


def test_second_run_is_idempotent(fixtures):
    args = (
        fixture_app(),
        date(2026, 10, 15),
        FixtureAppsFlyerClient(fixtures / "appsflyer"),
        FixtureAppleAdsClient(fixtures / "apple"),
    )
    a, b = run_app(*args), run_app(*args)
    assert [(p.keyword_id, p.proposed) for p in a.proposals] == [
        (p.keyword_id, p.proposed) for p in b.proposals
    ]
