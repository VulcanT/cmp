from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from cmp.config import Mode, Settings
from cmp.domain import Proposal, ProposalField, ProposalStatus
from cmp.executor.apple_writer import execute
from tests.conftest import make_keyword

GOLDEN = Path(__file__).parent / "golden_bulk_update.json"


def approved(kw, field, current, proposed, pid):
    return Proposal(
        kw.keyword_id,
        kw.ad_group_id,
        "r",
        1,
        field,
        current,
        proposed,
        date(2026, 10, 15),
        {"seen_bid": str(kw.bid), "seen_status": str(kw.status)},
        ProposalStatus.APPROVED,
        id=pid,
    )


class ExplodingClient:
    def bulk_update_keywords(self, *_a, **_k):
        raise AssertionError("must not be called in dry-run")

    query_keywords = query_ad_groups = keyword_report = bulk_update_keywords


def test_dry_run_records_request_and_never_calls_client():
    k1, k2 = make_keyword(1, bid="1.00"), make_keyword(2, bid="1.00")
    props = [
        approved(k1, ProposalField.BID, "1.00", "1.15", 11),
        approved(k2, ProposalField.STATUS, "ENABLED", "PAUSED", 12),
    ]
    res = execute(props, {1: k1, 2: k2}, 999, ExplodingClient(), Settings(mode=Mode.DRY_RUN))
    assert len(res.executions) == 1 and res.executions[0].dry_run
    assert all(p.status is ProposalStatus.DRY_RUN for p in props)
    expected = json.loads(GOLDEN.read_text())
    assert res.executions[0].request == expected


def test_pending_proposals_are_ignored():
    k1 = make_keyword(1)
    p = approved(k1, ProposalField.BID, "1.00", "1.15", 1)
    p.status = ProposalStatus.PENDING
    res = execute([p], {1: k1}, 999, None, Settings(mode=Mode.DRY_RUN))
    assert res.executions == [] and res.applied == []


def test_drifted_keyword_is_skipped_rest_goes():
    k1, k2 = make_keyword(1, bid="1.00"), make_keyword(2, bid="1.00")
    p1, p2 = (
        approved(k1, ProposalField.BID, "1.00", "1.15", 1),
        approved(k2, ProposalField.BID, "1.00", "1.15", 2),
    )
    live = {1: make_keyword(1, bid="1.50"), 2: k2}  # someone changed kw 1 in the console
    res = execute([p1, p2], live, 999, None, Settings(mode=Mode.DRY_RUN))
    assert p1.status is ProposalStatus.FAILED and p1.reason == "drifted"
    assert [i["data"]["id"] for i in res.executions[0].request["items"]] == [2]


def test_guardrails_reapplied_in_executor():
    k1 = make_keyword(1, bid="1.00", default="1.00")
    p = approved(k1, ProposalField.BID, "1.00", "5.00", 1)  # a bad proposal slipped through
    res = execute([p], {1: k1}, 999, None, Settings(mode=Mode.DRY_RUN))
    assert res.executions[0].request["items"][0]["data"]["bid"]["amount"] == "1.25"


def test_live_mode_uses_client_and_maps_results():
    class FakeClient:
        def bulk_update_keywords(self, ad_account_id, body):
            return {
                "result": [
                    {"correlationId": 1, "success": True},
                    {"correlationId": 2, "success": False, "error": {"code": "X"}},
                ]
            }

    k1, k2 = make_keyword(1), make_keyword(2)
    p1, p2 = (
        approved(k1, ProposalField.BID, "1.00", "1.10", 1),
        approved(k2, ProposalField.BID, "1.00", "1.10", 2),
    )
    res = execute([p1, p2], {1: k1, 2: k2}, 999, FakeClient(), Settings(mode=Mode.LIVE))
    assert p1.status is ProposalStatus.APPLIED and p2.status is ProposalStatus.FAILED
    assert res.executions[0].response is not None


def test_live_mode_without_client_raises():
    k1 = make_keyword(1)
    with pytest.raises(RuntimeError):
        execute(
            [approved(k1, ProposalField.BID, "1.00", "1.10", 1)],
            {1: k1},
            999,
            None,
            Settings(mode=Mode.LIVE),
        )
