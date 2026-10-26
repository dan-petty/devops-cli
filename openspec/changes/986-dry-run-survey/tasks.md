# Tasks

## 1. Enumerate and survey argument-taking commands

- [x] Enumerate all commands declaring `--dry-run` across the CLI tree and classify by argument requirements
  - Verification: script traverses Typer and Click tree, counting 51 argument-taking and 174 argument-free commands (total 225)
- [x] Execute all 51 argument-taking commands under `CliRunner` with recorder and network isolation
  - Verification: recorded child process invocations classified as local read, local write, or external
- [x] File roadmap candidate issues for identified offenders outside `commands/ci.py`
  - Verification: `uv run devops roadmap intake ... --confirm` filed #2312 and #2314
- [x] Document survey findings and command matrix in `design.md`
  - Verification: `design.md` contains 51-row matrix, methodology, and candidate citations
- [x] Validate OpenSpec change folder conformance
  - Verification: `uv run pytest tests/test_change_folders.py`
- [ ] Archive change folder upon completion
  - Verification: `uv run devops openspec archive 986-dry-run-survey`
