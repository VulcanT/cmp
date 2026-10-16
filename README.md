# CMP — Campaign Management Platform

Phase 1: measure Apple Search Ads keyword ROAS from AppsFlyer daily, propose keyword bid/status
changes from predefined rules, approve in a web page, apply via the Apple Ads Platform API.

Built AI-native: `CLAUDE.md` is the contract for coding agents, `specs/` is the product truth,
`.claude/` holds skills (API cheat-sheets, workflows), a reviewer subagent and hooks that gate on tests.

## Quick start
```bash
make setup            # venv + deps
make test             # 27 tests, no network
make daily-dry        # full pipeline on recorded fixtures, dry-run executor
make run              # http://localhost:8000/batches/2026-10-15 (needs DB rows)
```

## Status
| Area | State |
| --- | --- |
| Rule engine + guardrails | implemented, tested |
| Executor (dry-run, drift check, bulk-update body) | implemented, tested; live path tested with a fake client |
| Ingest parsers + reconcile | implemented against fixture shapes; AppsFlyer response shape must be confirmed against a real call |
| Approvals service + htmx page | minimal; no auth |
| Live clients | written, not yet exercised against real accounts |
| Scheduler, digest, DB persistence of pipeline output | not started (see `specs/`) |

## First three sessions with Claude Code
1. `Capture one real AppsFlyer Cohort API response for app <id> (kpi=revenue, 1 day) into tests/fixtures/appsflyer/real_sample.json using AF_API_TOKEN, then adapt parse_cohort to it and keep tests green.`
2. `Wire pipeline.main to persist keywords, keyword_daily and proposals via src/cmp/db (see specs/ingest.md, specs/approvals.md). Tests first.`
3. `Add the APScheduler job for 10:00 Australia/Sydney and the log-only digest (specs/approvals.md).`

Never set `CMP_MODE=live` until a dry-run batch has been reviewed in `executions` and one single-keyword live change has been confirmed in Apple Ads Change History.
