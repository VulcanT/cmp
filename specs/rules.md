# Spec: rules

## Goal
Turn `keyword_daily` into `Proposal`s using declarative YAML rules, bounded by global guardrails. The engine never calls external APIs.

Schema **v1** (`rules/example.yaml`, no `schema` key) is implemented. Schema **v2** (`schema: 2` at the top of the file) is a superset, specified on 2026-10-22 after the MobileAction CMP teardown (project doc `claude/mobileaction-teardown.md`): relative thresholds, a mandatory sample floor, CMP-side actions beside the Apple action, labels and scope, cooldowns, an install match-rate gate, and a run log with skip reasons. A file without `schema` is v1 and must keep loading unchanged; v2-only checks apply when `schema >= 2`.

## Inputs
- `rules/<app_id>.yaml`: `schema` (absent = 1), `app_id`, `targets` (`roas_d7`, `cpi`), `defaults`, `rules[]`. Numbers are parsed with `Decimal(str(v))`, like `targets`.
- The `apps` row for the app (`AppConfig`), passed to `RuleEngine`: currency and the attribution settings (specs/ingest.md), copied into every `evidence_json`. The YAML never carries attribution.
- `KeywordWindow` (7-day cumulative, plus 14-day for `*_14d`): everything v1 exposes, plus the v2 metrics below.
- Parent windows for the same dates: `ad_group` and `campaign` aggregates built by the window builder from `ad_group_daily` / `campaign_daily` (sum the 7 dates, then re-ratio), exposed as dicts so `campaign.cpa` works in `SafeExpr`. Apple-only ratios (`cpa`, `cpt`, `ttr`, `cr`) cover every keyword in the Apple report; AppsFlyer ratios (`roas_*`, `cpi`) cover only keywords with an AppsFlyer mapping, so unmapped spend does not deflate them.
- App-level gates computed by ingest: `app.match_rate_7d`.
- Labels: `labels` table (`entity_level`, `entity_id`, `label`), CMP-side only; Apple has no keyword labels. Labels are used by `scope`, not inside expressions (`SafeExpr` has no `in`).

### Rule schema v2
```yaml
schema: 2
app_id: example
targets: { roas_d7: 0.80, cpi: 3.00 }

rules:
  - id: cut_the_cost
    version: 1
    enabled: true                # default true; a disabled rule is loaded, validated and skipped
    scope:                       # optional; absent = every keyword of the app
      placement: SEARCH_RESULTS  # the only value in Phase 1
      level: keyword             # the only value in Phase 1
      in: { campaigns: [], ad_groups: [], labels: [generic] }   # any-of per list, all non-empty lists must match
    min_sample: apple_installs >= 5          # required in v2; failing it logs insufficient_sample
    when: cpa > 1.5 * campaign.cpa           # relative threshold = MobileAction "Advanced mode"
    guards: []                               # extra expressions; failing logs rule_guard
    cooldown_days: 3                         # default 1; failing logs cooldown
    actions:                                 # at most ONE Apple action (bid_pct | status) + any CMP-side actions (label, notify)
      - { bid_pct: -0.15, max_bid: 5.00 }
      - { notify: digest }
```
`action:` (v1, single Apple action) is still accepted and equals a one-item `actions:` list. The loader validates every name and `x.y` attribute in `min_sample`, `when` and `guards` against the namespace below at load time, so an unknown metric fails at startup, never on the first keyword.

Expression namespace (v1 names unchanged):

| Name | Meaning | Source |
| --- | --- | --- |
| `spend`, `af_cost`, `revenue_d7`, `roas_d7`, `cpi`, `days_active`, `last_change_days`, `spend_14d`, `installs_14d`, `current_bid`, `default_bid`, `status`, `cost_mismatch_pct`, `targets.*` | as v1 | — |
| `installs` | AppsFlyer `users` only; 0 when the keyword has no AppsFlyer row (the v1 fallback to Apple installs in `reconcile.py` is removed, or `match_rate_7d` reads 1.0 exactly when MMP data is missing) | AppsFlyer Cohort API |
| `impressions`, `taps`, `apple_installs` | Apple report sums; `apple_installs` = `tapInstalls` (not `totalInstalls`) | Apple keyword report |
| `cpt`, `ttr`, `cr`, `cpa` | `spend/taps`, `taps/impressions`, `apple_installs/taps`, `spend/apple_installs`; None on zero denominator | derived |
| `revenue_d1`, `revenue_d3`, `roas_d1`, `roas_d3` | extra cohort windows | AppsFlyer Cohort API |
| `match_rate_7d` | `installs / apple_installs` over the window; None when `apple_installs = 0` | derived |
| `ad_group.<name>`, `campaign.<name>` | same names, parent aggregate over the same dates | ingest aggregates |
| `app.match_rate_7d`, `app.target_roas_d7` | app-level | ingest / targets |
| `impression_share` | only once the Apple Ads Platform API is confirmed to expose an impression-share report — **verify**; until then the name is not in the namespace and the templates that use it are not shipped as files | Apple |

Actions: `bid_pct` (`+0.15`, optional `max_bid` / `min_bid` in the app currency), `status` (`PAUSED` / `ENABLED`), `label` (`{ label: add, value: watch }` / `remove`), `notify` (`digest` in Phase 1; `slack`, `email` later). Only `bid_pct` and `status` become `Proposal`s (one field each, so the one-proposal-per-keyword guardrail holds); `label` and `notify` are applied by the pipeline when the rule wins, never sent to Apple. A rule with only CMP-side actions produces no proposal.

## Behaviour
1. **Gates first, per keyword, before any rule.** `cost_mismatch`: `cost_mismatch_pct > Guardrails.max_cost_mismatch_pct` (0.05) → warning, no proposal (v1 behaviour; the code is renamed from `cost_mismatch_hold` to `cost_mismatch` everywhere, engine and reconcile alike). `match_rate_low`: `apple_installs >= Guardrails.min_installs_for_match_rate` (5) and `match_rate_7d < Guardrails.min_keyword_match_rate` (0.70), or `app.match_rate_7d < Guardrails.min_app_match_rate` (0.80) → warning, no proposal; a None match rate never holds. Rationale: under-counted MMP installs deflate ROAS and trigger false bid-downs. All four thresholds are `Guardrails` fields; ingest imports them from there.
2. **Scope.** A keyword is in scope when every non-empty list in `scope.in` matches (campaign id, ad group id, any label). Out of scope logs nothing. `enabled: false` rules are skipped and log nothing.
3. **Evaluate rules in file order.** For each rule: `min_sample` → `when` → `guards` → cooldown (`last_change_days >= cooldown_days`). The first rule whose chain passes **wins**: its Apple action becomes the keyword's one proposal and its CMP-side actions are applied. Remaining rules are still evaluated in shadow mode and logged `shadowed_by:<winner>` when they would have fired, so ordering can be tuned.
4. `bid_pct` → `proposed = round(current_bid * (1 + pct), 2)`, then the rule's own `max_bid` / `min_bid`, then global guardrails. A cap that would reverse the direction of the move (`max_bid < current_bid` on a bid-up, `min_bid > current_bid` on a bid-down) makes the rule a no-op, logged `rule_guard`. `status` → as v1. `label` → a `labels` write. `notify` → a digest line.
5. Guardrails (`guards.py`), applied in the engine and again in the executor — unchanged: one proposal per keyword per batch date; bid change within ±25% per day; bid within [0.3×, 2×] of the ad group default bid; at most 10% of an ad group's active keywords paused in one batch; a clamped no-op is dropped. A proposal dropped here turns the winner's log row into `skipped` with the `guard:*` reason.
6. Each proposal records `evidence_json`: the window values, parent aggregates used by the rule, rule id + version, bid/status seen, and `attribution` copied from the `apps` row (`cohort_type`, `time_basis`, `touch`, `touch_effective`).
7. **Run log.** Every keyword × rule evaluation writes a `rule_evaluations` row: `batch_date`, `app_id`, `keyword_id`, `rule_id`, `outcome` (`proposed` | `skipped` | `shadowed`), `reason` (`insufficient_sample`, `rule_when`, `rule_guard`, `cooldown`, `cost_mismatch`, `match_rate_low`, `guard:*` from guardrails, `shadowed_by:<rule_id>`), `detail` (the failing expression and the values it saw). Gate holds write one row with `rule_id = null`. A re-run for a batch date replaces that date's rows. The approvals page shows a "full log" filtered by keyword, rule or reason.
8. Recommended file order, mirroring MobileAction's templates: pauses → bid-downs → bid-ups (larger step first) → notify-only.

## Templates
`rules/templates/<name>.yaml` ships one file per Phase 1 template; copy-paste the rule into an app file (a CLI can come later). Ported from MobileAction's catalogue; thresholds are their defaults and are tuning parameters. "×" = multiple of the campaign average.

| Template | min_sample | when | actions | Phase |
| --- | --- | --- | --- | --- |
| `waste_broker` | `taps > 10` | `apple_installs < 1` | pause | 1 |
| `revenue_guardian` | `spend >= 25` | `revenue_d7 == 0` | pause | 1 |
| `loser_killer` | `impressions > 500` | `ttr < 0.03` | pause, notify | 1 |
| `cut_the_cost` | `apple_installs >= 5` | `cpa > 1.5 * campaign.cpa` | bid −15% | 1 |
| `penny_wise` | `apple_installs >= 5` | `cpa > 1.0 * campaign.cpa` | bid −5% | 1 |
| `roas_rocket` | `installs >= 10 and revenue_d7 > 0` | `roas_d7 >= 2.0 * campaign.roas_d7` | bid +20% | 1 |
| `roas_rush` | `installs >= 10 and revenue_d7 > 0` | `roas_d7 >= 1.0 * campaign.roas_d7` | bid +10% | 1 |
| `impression_generator` | — (`impressions >= 0`) | `impressions < 50 and days_active >= 7` | bid +10% | 1 |
| `cost_spy` | `installs >= 5` | `cpi > 2.0 * targets.cpi` | notify | 1 |
| `performance_pulse` | `taps > 200` | `cr < 0.02` | notify | 1 |
| `install_mania` / `install_miner` / `capture_the_crown` | `apple_installs > 5` (crown: `> 100`) | CPA or ROAS vs campaign **and** `impression_share < 0.80` | bid +20% / +10% / +20% | not shipped until `impression_share` is verified |
| `event_maximiser` / `volume_booster` / `cost_ninja` / `coast_cruncher` | `goals > 3` | cost-per-goal vs campaign | bid ±5–20% | 2 (needs goal-event KPI from Cohort API) |
| `feed_the_beast` / `on_the_safe_side` | ad-group level | installs/CPA, spend/goals | default CPT ±10% / −5% | 2 (ad-group actions) |
| `seek_and_love` / `waste_terminator` | search-term level | `ttr > 0.05 and cr > 0.50` / inverse | add exact keyword / add negative | 2 (search-term report + negative-keyword calls — verify in the Platform API skill) |
| `budget_watchdog` / `boost_the_beast` | campaign level | `spend > 0.9 * daily_budget` | notify / daily budget +$100 | 3 (budget actions) |

The v1 starter rules (`scale_winner`, `trim_loser`, `pause_dead`) stay valid; they are target-based while the templates are campaign-relative, and an app file may mix both.

## Acceptance criteria
- `tests/rules/test_loader.py`: a file without `schema` loads unchanged; a `schema: 2` rule without `min_sample` is rejected with a clear error; two Apple actions in one rule, or a repeated action kind, is rejected; an unknown metric name is rejected at load; `campaign.cpa` resolves through `SafeExpr`.
- `tests/rules/test_engine.py` (existing cases plus): relative threshold fires against the campaign aggregate; `insufficient_sample`, `cooldown`, `match_rate_low` (keyword and app) each produce the matching `rule_evaluations` reason and no proposal; a keyword with `apple_installs < 5` is never held by `match_rate_low`; a second matching rule is logged `shadowed_by`; `max_bid` caps before guardrails and a direction-reversing cap is a `rule_guard` no-op; a notify-only rule yields a digest line and no proposal; label scope excludes an unlabelled keyword; `evidence_json.attribution` equals the `AppConfig` values.
- A fixture-based test per shipped Phase 1 template (`tests/rules/templates/`), one firing and one non-firing keyword each.

## Out of scope
LLM-generated rules; search-term mining, negative keywords, ad-group and campaign-level actions (Phase 2–3, see Templates); Slack/email transports; impression share until verified.

## Verification
`pytest tests/rules -q` green; `make daily-dry` prints proposals **and** the evaluation log summary (counts by outcome and reason) for the fixture app.
