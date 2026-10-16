from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cmp.domain import Keyword, KeywordStatus, KeywordWindow

os.environ.setdefault("CMP_DATABASE_URL", "sqlite://")
os.environ.setdefault("CMP_MODE", "dry_run")

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


def make_keyword(
    kid: int = 1,
    bid: str = "1.00",
    default: str = "1.00",
    status: str = "ENABLED",
    ad_group: int = 10,
) -> Keyword:
    return Keyword(
        kid,
        ad_group,
        100,
        f"kw{kid}",
        "EXACT",
        Decimal(bid),
        "USD",
        KeywordStatus(status),
        Decimal(default),
    )


def make_window(
    kw: Keyword,
    spend: str = "0",
    installs: int = 0,
    revenue_d7: str = "0",
    days_active: int = 30,
    last_change_days: int = 30,
    spend_14d: str | None = None,
    installs_14d: int | None = None,
    af_cost: str | None = None,
) -> KeywordWindow:
    return KeywordWindow(
        keyword=kw,
        days=7,
        spend=Decimal(spend),
        af_cost=Decimal(af_cost if af_cost is not None else spend),
        installs=installs,
        revenue_d7=Decimal(revenue_d7),
        days_active=days_active,
        last_change_days=last_change_days,
        spend_14d=Decimal(spend_14d if spend_14d is not None else spend),
        installs_14d=installs_14d if installs_14d is not None else installs,
    )


@pytest.fixture
def batch_date() -> date:
    return date(2026, 10, 15)
