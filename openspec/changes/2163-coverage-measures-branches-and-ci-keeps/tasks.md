# Tasks

## 1. Enable branch coverage in pyproject.toml

Reads: none. Changes: `pyproject.toml`.

- [ ] 1.1 Write a test in tests/test_coverage_config.py. The test reads pyproject.toml with tomllib, parses the [tool.coverage.run] table, and asserts that the key `branch` has the value `True`. The test fails before the change because the key is absent, and verify that `uv run devops ci test tests/test_coverage_config.py` fails on the base
- [ ] 1.2 Add `branch = true` to the [tool.coverage.run] section of pyproject.toml, after the existing `parallel = true` line, and verify that `uv run devops ci test tests/test_coverage_config.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Upload coverage XML as CI artifact

Reads: none. Changes: `.github/workflows/ci.yml`.

- [ ] 2.1 Write a test in tests/test_workflows.py. The test reads .github/workflows/ci.yml with yaml.safe_load, finds the job whose `name` is `Tests & Coverage`, and asserts that one of its steps has `uses` starting with `actions/upload-artifact@` and a `with` table containing `path` set to `.data/coverage.xml` and a `retention-days` key. The test fails before the change because no such step exists, and verify that `uv run devops ci --check --only actionlint,zizmor` fails on the base
- [ ] 2.2 Add a step after the Changed-Line Coverage step in the Tests & Coverage job: name `Upload Coverage XML`, uses `actions/upload-artifact` pinned by commit SHA, with `name: coverage-xml`, `path: .data/coverage.xml`, and `retention-days: 7`. Add `if: always()` so the artifact uploads even when the gate fails, and verify that `uv run devops ci --check --only actionlint,zizmor` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
