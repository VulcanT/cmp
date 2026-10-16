"""SQLAlchemy models. Postgres in prod, SQLite in tests. Migrations: alembic (to add)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class App(Base):
    __tablename__ = "apps"
    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[str] = mapped_column(String(64), unique=True)  # AppsFlyer app id
    ad_account_id: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    timezone: Mapped[str] = mapped_column(String(64), default="Australia/Sydney")
    enabled: Mapped[bool] = mapped_column(default=True)


class KeywordRow(Base):
    __tablename__ = "keywords"
    keyword_id: Mapped[int] = mapped_column(primary_key=True)
    ad_group_id: Mapped[int] = mapped_column(Integer, index=True)
    campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(String(255))
    match_type: Mapped[str] = mapped_column(String(16))
    bid: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16))
    ad_group_default_bid: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    first_seen: Mapped[date] = mapped_column(Date)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KeywordDailyRow(Base):
    __tablename__ = "keyword_daily"
    __table_args__ = (UniqueConstraint("keyword_id", "cohort_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.keyword_id"), index=True)
    cohort_date: Mapped[date] = mapped_column(Date, index=True)
    af_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    asa_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    installs: Mapped[int] = mapped_column(Integer)
    revenue_d0: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    revenue_d7: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    taps: Mapped[int] = mapped_column(Integer)
    impressions: Mapped[int] = mapped_column(Integer)
    pulled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProposalRow(Base):
    __tablename__ = "proposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.keyword_id"), index=True)
    ad_group_id: Mapped[int] = mapped_column(Integer)
    rule_id: Mapped[str] = mapped_column(String(64))
    rule_version: Mapped[int] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(16))
    current: Mapped[str] = mapped_column(String(32))
    proposed: Mapped[str] = mapped_column(String(32))
    batch_date: Mapped[date] = mapped_column(Date, index=True)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DecisionRow(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), unique=True)
    decided_by: Mapped[str] = mapped_column(String(128))
    decision: Mapped[str] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ExecutionRow(Base):
    __tablename__ = "executions"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(Integer)
    proposal_ids: Mapped[list[int]] = mapped_column(JSON)
    request: Mapped[dict[str, object]] = mapped_column(JSON)
    response: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    dry_run: Mapped[bool] = mapped_column(default=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
