# CMP — Campaign Management Platform (Phase 1: AppsFlyer → Apple Search Ads)

Python 3.12+, FastAPI, SQLAlchemy, Postgres (SQLite in tests), htmx UI. Package: `src/cmp`.

## Commands
- `make setup` — create venv and install (`pip install -e ".[dev]"`)
- `make test` — `pytest -q` (must be green before any task is "done")
- `make lint` — `ruff check . && ruff format --check . && mypy src`
- `make run` — `uvicorn cmp.app:app --reload`
- `make daily-dry` — run the daily pipeline in dry-run against recorded fixtures

## Invariants (never break these)
1. IMPORTANT: Nothing writes to Apple Ads unless a `Proposal` has `status=approved` and `CMP_MODE=live`. Default is `dry_run`.
2. No secrets in code or fixtures. Credentials come from env vars named in `.env.example`.
3. Every behaviour change ships with a test. Rule logic changes ship with a fixture-based test in `tests/rules/`.
4. Guardrails in `src/cmp/rules/guards.py` are enforced again in the executor; do not remove either copy.

## Conventions
- Specs in `specs/` are the source of truth. Read the spec for the module before editing it; update the spec if behaviour changes.
- Rules are YAML in `rules/<app_id>.yaml`; engine code must stay generic (no app-specific branches).
- Keyword text is normalised to lowercase everywhere (AppsFlyer drops cost for keywords with uppercase letters).
- Money is `Decimal` with currency; never float.
- Dates are cohort dates in the app's timezone; store as `date`, not `datetime`.
- External calls go through `src/cmp/clients/` only; tests use recorded JSON fixtures in `tests/fixtures/`, never the network.

## Workflow
- Multi-file change: plan first, then implement, then `make test`, then ask for review via the `reviewer` subagent.
- One-line fix: just do it and run the affected test.
- Editing `src/cmp/executor/` requires `ALLOW_EXECUTOR_EDIT=1` (hook enforced).
- When compacting, preserve the list of modified files and the test command.

## Gotchas
- Apple Ads Platform API: every call needs `X-AP-Context: adAccountId=<id>`; respect `RateLimit-*` and `Retry-After` headers; keyword PUT accepts only `bid` and `status`.
- AppsFlyer Cohort API: exactly one KPI per call besides the always-on `users, ecpi, cost`; 60 calls/min; date range ≤ 31 days.
- Campaign Management API v5 is sunset 2027-01-26. Do not add code against `api.searchads.apple.com`.
