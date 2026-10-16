"""Daily pipeline: ingest → reconcile → rules → proposals (→ dry-run executor when run manually).

Run: `python -m cmp.pipeline --date 2026-10-14` or `--date yesterday`.
With CMP_FIXTURES=1 it reads tests/fixtures instead of calling APIs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from cmp.clients.apple_ads_client import AppleAdsClient, FixtureAppleAdsClient
from cmp.clients.appsflyer_client import AppsFlyerClient, FixtureAppsFlyerClient
from cmp.config import Settings, get_settings
from cmp.domain import Keyword, KeywordDaily, Proposal, Warning
from cmp.ingest.apple_reports import (
    parse_ad_group_default_bids,
    parse_keyword_report,
    parse_keywords,
)
from cmp.ingest.appsflyer import parse_cohort
from cmp.ingest.reconcile import build_windows, reconcile
from cmp.rules import RuleEngine, load_ruleset

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


@dataclass
class AppConfig:
    app_id: str
    ad_account_id: int
    campaign_ids: list[int]
    campaign_names: dict[int, str]
    rules_path: Path


@dataclass
class PipelineResult:
    keywords: list[Keyword] = field(default_factory=list)
    daily: list[KeywordDaily] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    dropped: list[Proposal] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
    unmapped: list[tuple[str, str, str]] = field(default_factory=list)


def run_app(
    app: AppConfig, as_of: date, af: AppsFlyerClient, asa: AppleAdsClient, lookback_days: int = 14
) -> PipelineResult:
    out = PipelineResult()
    names: dict[int, tuple[str, str]] = {}
    apple_daily = []
    start, end = as_of - timedelta(days=lookback_days), as_of - timedelta(days=1)

    for cid in app.campaign_ids:
        ad_groups = asa.query_ad_groups(app.ad_account_id, cid)
        default_bids = parse_ad_group_default_bids(ad_groups)
        group_names = {int(g["id"]): str(g["name"]) for g in ad_groups}
        kws, warns = parse_keywords(asa.query_keywords(app.ad_account_id, cid), default_bids)
        out.keywords.extend(kws)
        out.warnings.extend(warns)
        for kw in kws:
            names[kw.keyword_id] = (app.campaign_names[cid], group_names.get(kw.ad_group_id, ""))
        apple_daily.extend(
            parse_keyword_report(asa.keyword_report(app.ad_account_id, cid, start, end))
        )

    # One Cohort call per cohort day keeps revenue D0/D7 unambiguous (from == to).
    for i in range(lookback_days):
        day = start + timedelta(days=i)
        revenue_rows = parse_cohort(af.cohort(app.app_id, day, day, "revenue"), "revenue")
        rec = reconcile(out.keywords, names, apple_daily, revenue_rows, day)
        out.daily.extend(rec.daily)
        out.unmapped.extend(rec.unmapped)
        out.warnings.extend(rec.warnings)

    windows = build_windows(out.keywords, out.daily, as_of)
    engine = RuleEngine(load_ruleset(app.rules_path))
    res = engine.evaluate(windows, as_of)
    out.proposals, out.dropped = res.proposals, res.dropped
    out.warnings.extend(res.warnings)
    return out


def fixture_app() -> AppConfig:
    cfg: dict[str, Any] = json.loads((FIXTURES / "app.json").read_text())
    return AppConfig(
        app_id=cfg["app_id"],
        ad_account_id=int(cfg["ad_account_id"]),
        campaign_ids=[int(c) for c in cfg["campaign_names"]],
        campaign_names={int(k): v for k, v in cfg["campaign_names"].items()},
        rules_path=Path(__file__).resolve().parents[2] / "rules" / "example.yaml",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="yesterday")
    args = parser.parse_args(argv)
    settings: Settings = get_settings()
    as_of = (
        date.today()
        if args.date == "yesterday"
        else date.fromisoformat(args.date) + timedelta(days=1)
    )

    if not settings.use_fixtures:
        raise SystemExit("Live ingest is not wired yet: set CMP_FIXTURES=1 (see specs/ingest.md).")
    af: AppsFlyerClient = FixtureAppsFlyerClient(FIXTURES / "appsflyer")
    asa: AppleAdsClient = FixtureAppleAdsClient(FIXTURES / "apple")
    app = fixture_app()
    as_of = (
        date.fromisoformat(json.loads((FIXTURES / "app.json").read_text())["as_of"])
        if args.date == "yesterday"
        else as_of
    )
    res = run_app(app, as_of, af, asa)

    print(
        f"mode={settings.mode} as_of={as_of} keywords={len(res.keywords)} daily_rows={len(res.daily)}"
    )
    seen: set[tuple[str, int]] = set()
    for w in res.warnings:
        if (w.code, w.keyword_id) in seen:
            continue
        seen.add((w.code, w.keyword_id))
        print(f"  warn {w.code} kw={w.keyword_id}: {w.message}")
    for u in res.unmapped:
        print(f"  unmapped {u}")
    print(f"proposals={len(res.proposals)} dropped={len(res.dropped)}")
    for p in res.proposals:
        print(f"  {p.rule_id:14s} kw={p.keyword_id} {p.field}: {p.current} -> {p.proposed}")
    for p in res.dropped:
        print(f"  dropped {p.rule_id} kw={p.keyword_id}: {p.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
