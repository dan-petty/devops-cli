# Tasks

## 1. Audit record

- [x] 1.1 Write `audit.md` with the census, one decision row for each place, and the corrected claims of the issue body
  - Verification: `$ uv run devops openspec check`
- [x] 1.2 Confirm that the audit changes no file under `src/`
  - Verification: `$ git diff --quiet origin/main -- src/`
