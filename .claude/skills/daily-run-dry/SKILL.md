---
name: daily-run-dry
description: Run the full daily pipeline (ingest → rules → proposals → dry-run executor) against recorded fixtures and summarise the result. Invoke as /daily-run-dry.
disable-model-invocation: true
---
1. Run `make daily-dry`.
2. Summarise: rows in keyword_daily, warnings (uppercase keywords, cost mismatches, unmapped rows), proposals per rule, and the dry-run request JSON written to `executions`.
3. If anything errored, locate the failing step, propose a fix, and do not touch `src/cmp/executor/` without asking.
