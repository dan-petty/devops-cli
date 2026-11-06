# Tasks

## 1. The rule documents name real files (other)

- [x] 1.1 Add the failing tests: `.devops/review.md` in `CONST_DELETED_PROCESS_TERMS`, and the check of backticked `tests/` paths with its two negative controls, in `tests/invariants/test_agents_md_claims.py`.
  Verification: `uv run pytest tests/invariants/test_agents_md_claims.py` fails for `AGENTS.md` and for the moved test paths before the document fix
- [x] 1.2 Name `.devops/review.toml` in the review row of `AGENTS.md`
  Verification: `grep -n '\.devops/review\.md' AGENTS.md` prints nothing
- [x] 1.3 Note the retirement by #1916 in the calibration record of session `20260927-150737` in `docs/SELF_IMPROVEMENT.md`
  Verification: `grep -n 'retired that file' docs/SELF_IMPROVEMENT.md`
- [x] 1.4 State the mirror layout and give each moved test file its real path in `docs/TESTING.md`
  Verification: `grep -c flat docs/TESTING.md` prints 0, and `uv run pytest tests/invariants/test_agents_md_claims.py` passes
- [x] 1.5 Check that the change folder is valid
  Verification: `uv run devops openspec check`
