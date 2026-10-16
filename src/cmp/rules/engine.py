"""Rule engine: KeywordWindow[] + RuleSet → Proposal[] (+ warnings). No I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from cmp.domain import (
    KeywordWindow,
    Proposal,
    ProposalField,
    Warning,
    money,
)
from cmp.rules.guards import Guardrails, apply_guardrails
from cmp.rules.loader import Rule, RuleSet

MISMATCH_THRESHOLD = Decimal("0.05")


@dataclass
class EngineResult:
    proposals: list[Proposal] = field(default_factory=list)
    dropped: list[Proposal] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)


class RuleEngine:
    def __init__(self, ruleset: RuleSet, guardrails: Guardrails | None = None) -> None:
        self.ruleset = ruleset
        self.guardrails = guardrails or Guardrails()

    def namespace(self, w: KeywordWindow) -> dict[str, object]:
        return {
            "targets": self.ruleset.targets,
            "spend": w.spend,
            "af_cost": w.af_cost,
            "installs": w.installs,
            "revenue_d7": w.revenue_d7,
            "roas_d7": w.roas_d7,
            "cpi": w.cpi,
            "days_active": w.days_active,
            "last_change_days": w.last_change_days,
            "spend_14d": w.spend_14d,
            "installs_14d": w.installs_14d,
            "current_bid": w.keyword.bid,
            "default_bid": w.keyword.ad_group_default_bid,
            "status": str(w.keyword.status),
            "cost_mismatch_pct": w.cost_mismatch_pct,
        }

    def evaluate(self, windows: list[KeywordWindow], batch_date: date) -> EngineResult:
        result = EngineResult()
        raw: list[Proposal] = []
        for w in windows:
            mismatch = w.cost_mismatch_pct
            if mismatch is not None and mismatch > MISMATCH_THRESHOLD:
                result.warnings.append(
                    Warning(
                        w.keyword.keyword_id,
                        "cost_mismatch_hold",
                        f"AppsFlyer cost differs from Apple spend by {mismatch:.1%}; no rule applied",
                    )
                )
                continue
            ns = self.namespace(w)
            for rule in self.ruleset.rules:
                if not rule.when.eval(ns):
                    continue
                if not all(g.eval(ns) for g in rule.guards):
                    continue
                p = self._propose(rule, w, batch_date, ns)
                if p is not None:
                    raw.append(p)
                break  # first firing rule wins
        keywords = {w.keyword.keyword_id: w.keyword for w in windows}
        for p in apply_guardrails(raw, keywords, self.guardrails):
            (result.dropped if p.reason else result.proposals).append(p)
        return result

    def _propose(
        self, rule: Rule, w: KeywordWindow, batch_date: date, ns: dict[str, object]
    ) -> Proposal | None:
        kw = w.keyword
        evidence = {
            k: (str(v) if isinstance(v, Decimal) else v) for k, v in ns.items() if k != "targets"
        }
        evidence.update(
            {
                "rule": rule.id,
                "version": rule.version,
                "seen_bid": str(kw.bid),
                "seen_status": str(kw.status),
                "needs_review": rule.needs_review,
            }
        )
        if rule.action.kind == "bid_pct":
            proposed = money(kw.bid * (1 + Decimal(rule.action.value)))
            if proposed == money(kw.bid):
                return None
            return Proposal(
                kw.keyword_id,
                kw.ad_group_id,
                rule.id,
                rule.version,
                ProposalField.BID,
                str(money(kw.bid)),
                str(proposed),
                batch_date,
                evidence,
            )
        if rule.action.kind == "status":
            if rule.action.value == str(kw.status):
                return None
            return Proposal(
                kw.keyword_id,
                kw.ad_group_id,
                rule.id,
                rule.version,
                ProposalField.STATUS,
                str(kw.status),
                rule.action.value,
                batch_date,
                evidence,
            )
        return None
