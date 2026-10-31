# Tasks: Classify Scan Commands and Add Request Plans in Dry Run

- [x] Create `tests/commands/test_scan_dry_run.py` with failing tests for classifications and plans <!-- id: 0 -->
- [x] Implement `src/devops_cli/security/scan_plans.py` with `PlannedRequest` builders and shared command arguments <!-- id: 1 -->
- [x] Update result models in `src/devops_cli/models/vulnerability.py` and `src/devops_cli/security/pipeline.py` <!-- id: 2 -->
- [x] Decorate commands in `src/devops_cli/commands/scan.py` with dry-run classes and add plan rendering <!-- id: 3 -->
- [x] Remove echo-only previews and `--dry-run` options from read-only scan commands <!-- id: 4 -->
- [x] Remove 12 scan commands from `tests/fixtures/dry_run_gaps.json` <!-- id: 5 -->
- [x] Update `openspec/specs/command-dry-run-class/spec.md` with scan requirements <!-- id: 6 -->
- [x] Verify test suite and ratchet invariants pass <!-- id: 7 -->
- [x] Regenerate documentation with `devops docs generate --sync-readme` <!-- id: 8 -->
- [x] Archive change and verify static CI checks <!-- id: 9 -->
