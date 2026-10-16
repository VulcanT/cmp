"""Executor: approved Proposal[] → Apple Ads bulk-update. Dry-run by default.

Invariant (CLAUDE.md #1): only proposals with status=approved are considered, and nothing is
sent unless settings.mode == live. Guardrails are re-applied here; drifted keywords are skipped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from cmp.clients.apple_ads_client import AppleAdsClient
from cmp.config import Settings
from cmp.domain import Keyword, Proposal, ProposalField, ProposalStatus
from cmp.rules.guards import apply_guardrails

CHUNK = 500


@dataclass
class Execution:
    ad_account_id: int
    request: dict[str, Any]
    response: dict[str, Any] | None
    dry_run: bool


@dataclass
class ExecutionResult:
    executions: list[Execution] = field(default_factory=list)
    applied: list[Proposal] = field(default_factory=list)
    failed: list[Proposal] = field(default_factory=list)


def build_bulk_body(proposals: list[Proposal], keywords: dict[int, Keyword]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for p in proposals:
        kw = keywords[p.keyword_id]
        data: dict[str, Any] = {"id": p.keyword_id}
        if p.field is ProposalField.BID:
            data["bid"] = {"amount": p.proposed, "currency": kw.currency}
        else:
            data["status"] = p.proposed
        items.append({"correlationId": p.id if p.id is not None else p.keyword_id, "data": data})
    return {"allowPartialSuccess": True, "items": items}


def execute(
    proposals: list[Proposal],
    live_keywords: dict[int, Keyword],
    ad_account_id: int,
    client: AppleAdsClient | None,
    settings: Settings,
) -> ExecutionResult:
    result = ExecutionResult()
    approved = [p for p in proposals if p.status is ProposalStatus.APPROVED]
    if not approved:
        return result

    # 1. Drift check against the keyword as it is in Apple right now.
    ready: list[Proposal] = []
    for p in approved:
        kw = live_keywords.get(p.keyword_id)
        if kw is None:
            p.status, p.reason = ProposalStatus.FAILED, "missing_in_apple"
            result.failed.append(p)
            continue
        seen_bid, seen_status = p.evidence.get("seen_bid"), p.evidence.get("seen_status")
        if (seen_bid and str(kw.bid) != str(seen_bid)) or (
            seen_status and str(kw.status) != seen_status
        ):
            p.status, p.reason = ProposalStatus.FAILED, "drifted"
            result.failed.append(p)
            continue
        ready.append(p)

    # 2. Guardrails again (defence in depth).
    survivors: list[Proposal] = []
    for p in apply_guardrails(ready, live_keywords):
        if p.reason:
            p.status = ProposalStatus.FAILED
            result.failed.append(p)
        else:
            survivors.append(p)

    # 3. Bulk update in chunks; dry-run records the exact request and stops.
    for i in range(0, len(survivors), CHUNK):
        chunk = survivors[i : i + CHUNK]
        body = build_bulk_body(chunk, live_keywords)
        if not settings.is_live:
            result.executions.append(Execution(ad_account_id, body, None, dry_run=True))
            for p in chunk:
                p.status = ProposalStatus.DRY_RUN
            result.applied.extend(chunk)
            continue
        if client is None:
            raise RuntimeError("live mode requires an Apple Ads client")
        response = client.bulk_update_keywords(ad_account_id, body)
        result.executions.append(Execution(ad_account_id, body, response, dry_run=False))
        by_corr = {r.get("correlationId"): r for r in response.get("result", [])}
        for p, item in zip(chunk, body["items"], strict=True):
            r = by_corr.get(item["correlationId"], {})
            if r.get("success"):
                p.status = ProposalStatus.APPLIED
                result.applied.append(p)
            else:
                p.status, p.reason = ProposalStatus.FAILED, json.dumps(r.get("error", "unknown"))
                result.failed.append(p)
    return result
