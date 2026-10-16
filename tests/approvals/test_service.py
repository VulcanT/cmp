from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from cmp.approvals.service import AlreadyDecided, decide, list_batch
from cmp.db.models import Base, KeywordRow, ProposalRow


@pytest.fixture
def s():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            KeywordRow(
                keyword_id=1,
                ad_group_id=10,
                campaign_id=100,
                text="kw",
                match_type="EXACT",
                bid=1,
                currency="USD",
                status="ENABLED",
                ad_group_default_bid=1,
                first_seen=date(2026, 10, 1),
            )
        )
        session.add(
            ProposalRow(
                id=5,
                keyword_id=1,
                ad_group_id=10,
                rule_id="r",
                rule_version=1,
                field="bid",
                current="1.00",
                proposed="1.15",
                batch_date=date(2026, 10, 15),
                evidence={},
            )
        )
        session.commit()
        yield session


def test_decide_once_then_409(s):
    assert [p.id for p in list_batch(s, date(2026, 10, 15))] == [5]
    row = decide(s, 5, "approved", by="hoang")
    assert row.status == "approved"
    with pytest.raises(AlreadyDecided):
        decide(s, 5, "rejected", by="hoang")


def test_bad_decision_rejected(s):
    with pytest.raises(ValueError):
        decide(s, 5, "maybe", by="hoang")
