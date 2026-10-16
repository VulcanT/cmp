---
name: new-rule
description: Add or change a bidding rule in rules/<app_id>.yaml with a fixture-based test. Invoke as /new-rule <rule description>.
disable-model-invocation: true
---
Add a rule as described: $ARGUMENTS

1. Read `specs/rules.md` and `rules/example.yaml`.
2. Write the rule in YAML (id, version, when, action, guards). Keep the engine generic; do not add Python branches for one app.
3. Add a fixture under `tests/fixtures/rules/<rule_id>.json` with a KeywordWindow that fires and one that does not.
4. Add a test in `tests/rules/test_rules_yaml.py` asserting the proposal (field, proposed value after guardrails) and the non-firing case.
5. Run `pytest tests/rules -q` and `make daily-dry`; paste the proposals output.
6. Update the rule table in `specs/rules.md` if the rule is new.
