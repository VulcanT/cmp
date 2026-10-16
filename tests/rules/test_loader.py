from __future__ import annotations

from decimal import Decimal

import pytest

from cmp.rules.loader import SafeExpr, parse_ruleset


def test_safe_expr_evaluates_targets_and_none():
    e = SafeExpr("roas_d7 >= targets.roas_d7 * 1.5 and installs >= 20")
    ns = {"targets": {"roas_d7": Decimal("0.8")}, "installs": 25}
    assert e.eval({**ns, "roas_d7": Decimal("1.3")}) is True
    assert e.eval({**ns, "roas_d7": Decimal("1.1")}) is False
    assert e.eval({**ns, "roas_d7": None}) is False  # zero spend → no ROAS → never fires


def test_safe_expr_rejects_calls_and_imports():
    with pytest.raises(ValueError):
        SafeExpr("__import__('os').system('x')")
    with pytest.raises(ValueError):
        SafeExpr("max(spend, 1)")


def test_parse_ruleset_minimal():
    rs = parse_ruleset(
        {
            "app_id": "a",
            "targets": {"cpi": 3},
            "rules": [{"id": "r", "when": "spend > 1", "action": {"bid_pct": -0.1}}],
        }
    )
    assert rs.rules[0].action.kind == "bid_pct" and rs.targets["cpi"] == Decimal("3")
