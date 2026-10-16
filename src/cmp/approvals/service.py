"""Approval service over the proposals/decisions tables."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from cmp.db.models import DecisionRow, ProposalRow
from cmp.domain import ProposalStatus


class AlreadyDecided(Exception):
    pass


def list_batch(s: Session, batch_date: date) -> list[ProposalRow]:
    return list(s.scalars(select(ProposalRow).where(ProposalRow.batch_date == batch_date)))


def decide(
    s: Session, proposal_id: int, decision: str, by: str, note: str | None = None
) -> ProposalRow:
    if decision not in (ProposalStatus.APPROVED, ProposalStatus.REJECTED):
        raise ValueError(f"bad decision {decision}")
    p = s.get(ProposalRow, proposal_id)
    if p is None:
        raise KeyError(proposal_id)
    if p.status != ProposalStatus.PENDING:
        raise AlreadyDecided(proposal_id)
    p.status = decision
    s.add(DecisionRow(proposal_id=proposal_id, decided_by=by, decision=decision, note=note))
    s.flush()
    return p
