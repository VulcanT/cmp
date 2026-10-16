"""Load rules/<app_id>.yaml into typed Rule objects with a safe expression evaluator."""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

_BIN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_CMP = {
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


class SafeExpr:
    """Evaluates `metric >= targets.roas_d7 * 1.5 and installs >= 20` over a namespace.

    Only comparisons, arithmetic, and/or/not, names and `targets.<x>` attributes are allowed.
    A None metric (e.g. ROAS with zero spend) makes the whole comparison False.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self.tree = ast.parse(source, mode="eval")
        self._validate(self.tree.body)

    def _validate(self, node: ast.AST) -> None:
        allowed = (
            ast.BoolOp,
            ast.BinOp,
            ast.UnaryOp,
            ast.Compare,
            ast.Name,
            ast.Constant,
            ast.Attribute,
            ast.And,
            ast.Or,
            ast.Not,
            ast.Load,
            ast.USub,
        )
        for child in ast.walk(node):
            if (
                not isinstance(child, allowed)
                and type(child) not in _BIN
                and type(child) not in _CMP
            ):
                raise ValueError(f"Disallowed syntax in rule expression: {ast.dump(child)}")

    def eval(self, ns: dict[str, Any]) -> bool:
        return bool(self._ev(self.tree.body, ns))

    def _ev(self, node: ast.AST, ns: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return Decimal(str(node.value)) if isinstance(node.value, (int, float)) else node.value
        if isinstance(node, ast.Name):
            if node.id not in ns:
                raise KeyError(f"Unknown metric '{node.id}' in rule '{self.source}'")
            return ns[node.id]
        if isinstance(node, ast.Attribute):
            base = self._ev(node.value, ns)
            return base[node.attr] if isinstance(base, dict) else getattr(base, node.attr)
        if isinstance(node, ast.UnaryOp):
            v = self._ev(node.operand, ns)
            return (not v) if isinstance(node.op, ast.Not) else -v
        if isinstance(node, ast.BinOp):
            left, right = self._ev(node.left, ns), self._ev(node.right, ns)
            if left is None or right is None:
                return None
            return _BIN[type(node.op)](Decimal(str(left)), Decimal(str(right)))
        if isinstance(node, ast.BoolOp):
            vals = [self._ev(v, ns) for v in node.values]
            return all(vals) if isinstance(node.op, ast.And) else any(vals)
        if isinstance(node, ast.Compare):
            left = self._ev(node.left, ns)
            for op, comp in zip(node.ops, node.comparators, strict=True):
                right = self._ev(comp, ns)
                if left is None or right is None:
                    return False
                if isinstance(left, str) or isinstance(right, str):
                    ok = _CMP[type(op)](str(left), str(right))
                else:
                    ok = _CMP[type(op)](Decimal(str(left)), Decimal(str(right)))
                if not ok:
                    return False
                left = right
            return True
        raise ValueError(f"Unsupported node {type(node).__name__}")


@dataclass(frozen=True)
class Action:
    kind: str  # "bid_pct" | "status" | "hold"
    value: str  # "+0.15", "-0.20", "PAUSED", "ENABLED", ""


@dataclass(frozen=True)
class Rule:
    id: str
    version: int
    when: SafeExpr
    action: Action
    guards: list[SafeExpr] = field(default_factory=list)
    needs_review: bool = False


@dataclass(frozen=True)
class RuleSet:
    app_id: str
    targets: dict[str, Decimal]
    rules: list[Rule]


def _parse_action(raw: dict[str, Any]) -> Action:
    if "bid_pct" in raw:
        return Action("bid_pct", str(raw["bid_pct"]))
    if "status" in raw:
        return Action("status", str(raw["status"]).upper())
    if raw.get("hold"):
        return Action("hold", "")
    raise ValueError(f"Unknown action {raw}")


def parse_ruleset(data: dict[str, Any]) -> RuleSet:
    targets = {k: Decimal(str(v)) for k, v in (data.get("targets") or {}).items()}
    rules = [
        Rule(
            id=str(r["id"]),
            version=int(r.get("version", 1)),
            when=SafeExpr(str(r["when"])),
            action=_parse_action(r["action"]),
            guards=[SafeExpr(str(g)) for g in (r.get("guards") or [])],
            needs_review=bool(r.get("needs_review", False)),
        )
        for r in data.get("rules") or []
    ]
    return RuleSet(app_id=str(data["app_id"]), targets=targets, rules=rules)


def load_ruleset(path: str | Path) -> RuleSet:
    with open(path, encoding="utf-8") as f:
        return parse_ruleset(yaml.safe_load(f))
