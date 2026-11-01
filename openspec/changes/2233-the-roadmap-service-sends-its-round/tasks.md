# Tasks

## 1. Define the two Service gauges in instruments.py

Reads: none. Changes: `src/devops_cli/telemetry/instruments.py`.

- [ ] 1.1 Add a test that asserts SERVICE_PAUSED_UNTIL and GITHUB_GRAPHQL_REMAINING are in INSTRUMENTS, have kind GAUGE, and their names do not end in _total, and verify that `uv run devops ci test tests/test_telemetry_instruments.py` fails on the base
- [ ] 1.2 Add SERVICE_PAUSED_UNTIL (name devops_cli_service_paused_until_seconds, kind GAUGE, unit s) and GITHUB_GRAPHQL_REMAINING (name devops_cli_github_graphql_remaining, kind GAUGE, unit 1) Instrument definitions. Add both to the INSTRUMENTS tuple. Add both to __all__, and verify that `uv run devops ci test tests/test_telemetry_instruments.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Emit the two gauges from the Service round

Reads: none. Changes: `src/devops_cli/roadmap/run.py`.

- [ ] 2.1 Add a test that runs a Service round with a pause and asserts the captured gauge devops_cli_service_paused_until_seconds equals the pause end time. Add a test that runs a round with no pause and asserts the gauge is 0. Add a test that asserts the captured gauge devops_cli_github_graphql_remaining equals the remaining points, and verify that `uv run devops ci test tests/test_roadmap_run.py` fails on the base
- [ ] 2.2 Import emit and the two instruments from devops_cli.telemetry.instruments. At the point where the Service logs the round pause end time, call emit(SERVICE_PAUSED_UNTIL, paused_until). At the point where the Service logs the GraphQL budget, call emit(GITHUB_GRAPHQL_REMAINING, remaining_points), and verify that `uv run devops ci test tests/test_roadmap_run.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. List the two gauges in TELEMETRY.md

Reads: none. Changes: `docs/TELEMETRY.md`.

- [ ] 3.1 No code test; the acceptance criterion is that the metric table in docs/TELEMETRY.md contains rows for both gauge names, and verify that `uv run devops ci test tests/test_telemetry_instruments.py` fails on the base
- [ ] 3.2 Add a row for devops_cli_service_paused_until_seconds (Gauge, s, the Unix time the round pause ends or 0 when no pause holds) and a row for devops_cli_github_graphql_remaining (Gauge, 1, the GraphQL points left from each round's closing budget read) to the metric table, and verify that `uv run devops ci test tests/test_telemetry_instruments.py` passes
- [ ] 3.3 docs/TELEMETRY.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
