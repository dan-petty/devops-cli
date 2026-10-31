# Tasks

## 1. Implementation
- [x] 1.1 Create `src/devops_cli/cloudflare/cloudflare_plans.py` with plan generators for all 10 Cloudflare commands
- [x] 1.2 Update `src/devops_cli/commands/cloudflare.py` to annotate commands with `@dry_run_class("request-plan")`, add `--dry-run` where missing, and wire request planning
- [x] 1.3 Remove legacy echo-only previews in `src/devops_cli/commands/cloudflare.py`
- [x] 1.4 Remove the 10 Cloudflare commands from `tests/fixtures/dry_run_gaps.json`

## 2. Verification
- [x] 2.1 Add unit tests in `tests/commands/test_cloudflare_dry_run.py` verifying dry-run classifications, request plans, structured JSON outputs, and zero external network calls
- [x] 2.2 Verify ratchet tests and existing Cloudflare test suites pass
- [x] 2.3 Run full `devops ci` check
