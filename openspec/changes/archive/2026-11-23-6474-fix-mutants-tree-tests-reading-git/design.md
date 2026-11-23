# Design

## Decisions
- Implement `git_repo` fixture in `tests/support/git_repo.py` that intercepts Git calls with `git_fake`.
- Answer `git rev-parse HEAD` with a recorded commit SHA and avoid starting real Git processes.
- Exclude tests that need full Git history or read generated source from the mutation selection in `pyproject.toml`.

## Rejected alternatives
- Real Git repository in `tmp_path`: Rejected because ADR 0007 forbids real Git subprocesses in tests of source.
- Pytest markers for exclusions: Rejected because mutmut does not apply marker filters during test execution.
