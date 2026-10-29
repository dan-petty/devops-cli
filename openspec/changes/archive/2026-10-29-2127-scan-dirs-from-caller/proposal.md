# Proposal

## Why

Issue #2127, the follow-up of #2098: #2098 removed every direct read of the working directory from `ai/review/`, `review/` and `security/`, but some reads still happened through a default. `get_repo_origin_name()` with no root named the repository of the working directory of the process, and the PR review called it so. The scanner entry points took the relative path `.` as their default target. A caller that runs in another directory, such as a test, the MCP server or a worktree, then reviews or scans the wrong tree when it gives no path.

## What Changes

- The scanner entry points take their target from the caller, with no default: `run_trivy_scan`, `run_kubelinter_scan`, `run_pluto_scan`, `run_bandit_scan` and `run_dive_scan`, which the issue names, and also `run_gitleaks_scan`, `run_semgrep_scan`, `run_ruff_scan`, `run_uv_audit_scan`, `run_trivy_sbom` and `DependencyRemediator`, which had the same default. Every caller under `src/` already gave a target.
- `get_repo_origin_name` takes the root of its repository from the caller and reads only the origin remote of that root. It no longer reads `GITHUB_REPOSITORY`.
- A command that has no `--repo` reads the working directory one time and gives `find_repo_root(Path.cwd())`: `devops pr`, `devops gh`, `devops roadmap` and `devops review pr`. `fetch_pr_check_verdicts` and the PR review helper take that `checkout`, and `resolve_branch_pr_number` requires the owner and the repository, which both of its callers give.
- The ast-grep rule `review-cwd-read` also fails `DEFAULT_CURRENT_PATH` and a parameter default of `Path(".")` in the review and scanner modules. An invariant test holds the root parameter of `get_repo_origin_name` to no default.
- ARCHITECTURE.md (section 7.4) describes both guards.

A command with no `--repo`, run in a directory with no origin remote while `GITHUB_REPOSITORY` names a repository, now names no repository. So the change carries a delta of `review-workspace`. Every other command keeps its behavior.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-workspace`: the origin lookup takes its root from the caller, and the PR review and the check fallback read the origin of the checkout that the command gives.

## Impact

- `src/devops_cli/security/`: eleven entry points lose their `.` default.
- `src/devops_cli/core/repo.py`: `get_repo_origin_name` requires its root.
- `src/devops_cli/commands/pr.py`, `gh.py`, `roadmap.py`, `review.py`, `src/devops_cli/ai/review/runner.py`, `src/devops_cli/github/check_verdict.py`, `pr_monitor.py`: the command gives the root.
- `.ast-grep/rules/review-cwd-read.yml` and its rule tests, `tests/invariants/test_source_tree.py`, ARCHITECTURE.md.

## Feasibility

I confirmed the premise against the code at a0165a16:

- `grep -n 'def run_\(trivy\|kubelinter\|pluto\|bandit\|dive\)_scan' -A4 src/devops_cli/security/*.py` showed `target ... = DEFAULT_CURRENT_PATH` (`Path(".")`) in the five functions. `grep -rn DEFAULT_CURRENT_PATH src/devops_cli/security/` showed the same default in six more.
- An AST walk of `src/` and `tests/` found no call of a scanner entry point without a target, 15 calls of `get_repo_origin_name()` with no root (10 in `commands/pr.py`, and one each in `commands/gh.py`, `commands/roadmap.py`, `github/check_verdict.py`, `github/pr_monitor.py` and `ai/review/runner.py`), and three `DependencyRemediator()` in tests.
- `get_repo_origin_name` read `GITHUB_REPOSITORY` only when it got no root. `git grep GITHUB_REPOSITORY` found no test of it and no document. Each workflow that runs `devops` (`ci.yml`, `copilot-setup-steps.yml`, `defect-pr-hardening-audit.yml`, `fail-to-pass.yml`) checks out the repository first, and `actions/checkout` sets the origin remote.
- On the base, the new PR review test read the origin in the worktree that the process ran in, not in the checkout that it gave, and the new check-fallback test failed because `fetch_pr_check_verdicts` took no checkout.

## Existing Tool Considered

ast-grep (`ast-grep-cli`, already pinned and run by the `constructs` row and the `ast-grep-scan` commit hook) holds the scanner side: the rule `review-cwd-read` gets two more patterns and their rule tests. The origin lookup is in `core/repo.py`, where `find_repo_root` reads `Path.cwd()` on purpose, so an invariant test on the parse that `tests/invariants/test_source_tree.py` already makes holds it. The change deletes the `.` default of eleven entry points, the no-root default and the `GITHUB_REPOSITORY` fallback of `get_repo_origin_name`, and the unused origin read of `resolve_branch_pr_number`.
