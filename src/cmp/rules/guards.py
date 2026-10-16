"""Global guardrails. Applied by the rule engine AND re-applied by the executor.

Pure functions over domain objects so they can run anywhere without a DB.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from cmp.domain import Keyword, KeywordStatus, Proposal, ProposalField, ProposalStatus, money


@dataclass(frozen=True)
class Guardrails:
    max_bid_move_pct: Decimal = Decimal("0.25")  # ±25% per day
    min_bid_multiple: Decimal = Decimal("0.3")  # of ad group default bid
    max_bid_multiple: Decimal = Decimal("2.0")
    max_pause_share_per_ad_group: Decimal = Decimal("0.10")  # 10% of active keywords per batch
    min_bid_abs: Decimal = Decimal("0.05")


def clamp_bid(current: Decimal, proposed: Decimal, default_bid: Decimal, g: Guardrails) -> Decimal:
    lo = max(current * (1 - g.max_bid_move_pct), default_bid * g.min_bid_multiple, g.min_bid_abs)
    hi = min(current * (1 + g.max_bid_move_pct), default_bid * g.max_bid_multiple)
    if hi < lo:  # caps disagree: do not move
        return money(current)
    return money(min(max(proposed, lo), hi))


def apply_guardrails(
    proposals: list[Proposal], keywords: dict[int, Keyword], g: Guardrails | None = None
) -> list[Proposal]:
    """Returns the surviving proposals (clamped, deduped, pause-share capped).

    Dropped proposals are returned with status=failed and a reason so callers can log them.
    """
    g = g or Guardrails()
    out: list[Proposal] = []
    seen: set[int] = set()
    paused_by_group: dict[int, int] = defaultdict(int)
    active_by_group: dict[int, int] = defaultdict(int)
    for kw in keywords.values():
        if kw.status is KeywordStatus.ENABLED:
            active_by_group[kw.ad_group_id] += 1

    for p in proposals:
        kw = keywords.get(p.keyword_id)
        if kw is None:
            p.status, p.reason = ProposalStatus.FAILED, "guard:unknown_keyword"
            out.append(p)
            continue
        if p.keyword_id in seen:
            p.status, p.reason = ProposalStatus.FAILED, "guard:one_per_keyword"
            out.append(p)
            continue
        seen.add(p.keyword_id)

        if p.field is ProposalField.BID:
            clamped = clamp_bid(kw.bid, Decimal(p.proposed), kw.ad_group_default_bid, g)
            if clamped == money(kw.bid):
                p.status, p.reason = ProposalStatus.FAILED, "guard:no_op_after_clamp"
                out.append(p)
                continue
            p.proposed = str(clamped)
        elif p.field is ProposalField.STATUS and p.proposed == KeywordStatus.PAUSED:
            allowed = int(active_by_group[kw.ad_group_id] * g.max_pause_share_per_ad_group)
            if paused_by_group[kw.ad_group_id] >= max(allowed, 1):
                p.status, p.reason = ProposalStatus.FAILED, "guard:pause_share"
                out.append(p)
                continue
            paused_by_group[kw.ad_group_id] += 1
        out.append(p)
    return out
