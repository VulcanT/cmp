"""Plain domain types shared by ingest, rules and executor. No ORM here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

CENT = Decimal("0.01")


def money(value: str | float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


class KeywordStatus(StrEnum):
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"


class ProposalField(StrEnum):
    BID = "bid"
    STATUS = "status"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DRY_RUN = "dry_run"
    APPLIED = "applied"
    FAILED = "failed"


@dataclass(frozen=True)
class Keyword:
    keyword_id: int
    ad_group_id: int
    campaign_id: int
    text: str
    match_type: str
    bid: Decimal
    currency: str
    status: KeywordStatus
    ad_group_default_bid: Decimal


@dataclass(frozen=True)
class KeywordDaily:
    keyword_id: int
    cohort_date: date
    af_cost: Decimal
    asa_spend: Decimal
    installs: int
    revenue_d0: Decimal
    revenue_d7: Decimal
    taps: int
    impressions: int

    @property
    def roas_d7(self) -> Decimal | None:
        if self.asa_spend == 0:
            return None
        return (self.revenue_d7 / self.asa_spend).quantize(Decimal("0.0001"))

    @property
    def cost_mismatch_pct(self) -> Decimal | None:
        if self.asa_spend == 0:
            return None
        return (abs(self.af_cost - self.asa_spend) / self.asa_spend).quantize(Decimal("0.0001"))


@dataclass(frozen=True)
class KeywordWindow:
    """Aggregates the rule engine evaluates. Built from KeywordDaily rows + the Keyword."""

    keyword: Keyword
    days: int
    spend: Decimal
    af_cost: Decimal
    installs: int
    revenue_d7: Decimal
    days_active: int
    last_change_days: int
    spend_14d: Decimal = Decimal("0")
    installs_14d: int = 0

    @property
    def roas_d7(self) -> Decimal | None:
        if self.spend == 0:
            return None
        return (self.revenue_d7 / self.spend).quantize(Decimal("0.0001"))

    @property
    def cpi(self) -> Decimal | None:
        if self.installs == 0:
            return None
        return money(self.spend / self.installs)

    @property
    def cost_mismatch_pct(self) -> Decimal | None:
        if self.spend == 0:
            return None
        return (abs(self.af_cost - self.spend) / self.spend).quantize(Decimal("0.0001"))


@dataclass
class Proposal:
    keyword_id: int
    ad_group_id: int
    rule_id: str
    rule_version: int
    field: ProposalField
    current: str
    proposed: str
    batch_date: date
    evidence: dict[str, Any] = field(default_factory=dict)
    status: ProposalStatus = ProposalStatus.PENDING
    id: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Warning:
    keyword_id: int
    code: str
    message: str
