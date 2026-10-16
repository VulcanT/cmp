from __future__ import annotations

from pathlib import Path

import pytest

from cmp.domain import ProposalField
from cmp.rules import RuleEngine, load_ruleset
from tests.conftest import make_keyword, make_window

RULES = Path(__file__).resolve().parents[2] / "rules" / "example.yaml"


@pytest.fixture
def engine() -> RuleEngine:
    return RuleEngine(load_ruleset(RULES))


def test_winner_is_scaled_15pct(engine, batch_date):
    kw = make_keyword(bid="1.00")
    res = engine.evaluate([make_window(kw, spend="14", installs=28, revenue_d7="140")], batch_date)
    assert [(p.rule_id, p.field, p.proposed) for p in res.proposals] == [
        ("scale_winner", ProposalField.BID, "1.15")
    ]
    assert res.proposals[0].evidence["seen_bid"] == "1.00"


def test_loser_is_trimmed_20pct(engine, batch_date):
    kw = make_keyword(bid="1.00")
    res = engine.evaluate([make_window(kw, spend="14", installs=14, revenue_d7="1.4")], batch_date)
    assert [(p.rule_id, p.proposed) for p in res.proposals] == [("trim_loser", "0.80")]


def test_dead_keyword_is_paused_before_trim(engine, batch_date):
    kw = make_keyword(bid="0.50")
    res = engine.evaluate(
        [make_window(kw, spend="21", installs=0, spend_14d="42", installs_14d=0)], batch_date
    )
    assert [(p.rule_id, p.field, p.proposed) for p in res.proposals] == [
        ("pause_dead", ProposalField.STATUS, "PAUSED")
    ]


def test_cost_mismatch_holds_everything(engine, batch_date):
    kw = make_keyword()
    res = engine.evaluate(
        [make_window(kw, spend="14", installs=28, revenue_d7="140", af_cost="10")], batch_date
    )
    assert res.proposals == []
    assert [w.code for w in res.warnings] == ["cost_mismatch_hold"]


def test_thin_data_does_not_fire(engine, batch_date):
    kw = make_keyword()
    res = engine.evaluate([make_window(kw, spend="2", installs=3, revenue_d7="20")], batch_date)
    assert res.proposals == [] and res.dropped == []


def test_recent_change_guard_blocks(engine, batch_date):
    kw = make_keyword()
    res = engine.evaluate(
        [make_window(kw, spend="14", installs=28, revenue_d7="140", last_change_days=1)], batch_date
    )
    assert res.proposals == []


def test_bid_at_cap_is_dropped_as_no_op(engine, batch_date):
    kw = make_keyword(bid="2.00", default="1.00")
    res = engine.evaluate([make_window(kw, spend="14", installs=28, revenue_d7="140")], batch_date)
    assert res.proposals == []
    assert [p.reason for p in res.dropped] == ["guard:no_op_after_clamp"]


def test_pause_share_capped_per_ad_group(engine, batch_date):
    kws = [make_keyword(kid=i, bid="0.50", ad_group=7) for i in range(1, 11)]
    windows = [make_window(k, spend="21", installs=0, spend_14d="42", installs_14d=0) for k in kws]
    res = engine.evaluate(windows, batch_date)
    assert len(res.proposals) == 1  # 10% of 10 active keywords
    assert all(p.reason == "guard:pause_share" for p in res.dropped) and len(res.dropped) == 9


def test_evaluate_is_deterministic(engine, batch_date):
    kw = make_keyword(bid="1.00")
    w = make_window(kw, spend="14", installs=28, revenue_d7="140")
    a, b = engine.evaluate([w], batch_date), engine.evaluate([w], batch_date)
    assert [p.proposed for p in a.proposals] == [p.proposed for p in b.proposals]
