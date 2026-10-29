# Design

## Context

#2098 made the command layer read the working directory one time and give it down to the review and the scanners, and the ast-grep rule `review-cwd-read` holds `Path.cwd()` and `os.getcwd()` out of `ai/review/`, `review/` and `security/`. Two reads stayed outside what that rule sees: the `.` default of the scanner entry points, and the no-root default of `get_repo_origin_name` in `core/repo.py`. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- No scanner entry point and no review or scanner module has a default that is the working directory, and the rule holds this.
- `get_repo_origin_name` takes its root from the caller, and every caller gives one. An invariant test holds the parameter.
- Each command that names a repository with no `--repo` keeps its behavior.

**Non-Goals:**

- `find_repo_root()` and `find_worktree_root()` keep their default. They are the helpers that the command layer calls to find the root from the working directory.
- `_resolve_current_git_branch` in `github/pr_monitor.py` reads the branch of the working directory through git. It has no directory parameter, and the issue does not name it.

## Decisions

- **All the scanner entry points, not five.** The issue names the five functions that its grep found. Six more had the same default: `run_gitleaks_scan`, `run_semgrep_scan`, `run_ruff_scan`, `run_uv_audit_scan`, `run_trivy_sbom` and the constructor of `DependencyRemediator`. Every caller under `src/` gives them a target, and three tests change. Rejected: the five alone. The same read stays in six functions, and the guard needs a list of names instead of a rule.
- **The caller gives the root, and the lookup does not walk up.** The command gives `find_repo_root(Path.cwd())`, which was the default. Rejected: a lookup that walks up from any directory. It changes explicit callers: `refine.inspect_checkout` of a directory inside another checkout, such as a clone under the data directory (#1358), would name the origin of the outer checkout.
- **No `GITHUB_REPOSITORY` fallback.** The lookup read it only when it got no root. Each workflow that runs `devops` checks out the repository, and `actions/checkout` sets the origin remote, so no workflow reaches it. No test or document named it. Rejected: the fallback for every root. A temporary directory of a test on a GitHub runner would then name the repository of the workflow, which is why the fallback applied only with no root. Rejected: the fallback in the command layer. It adds 13 copies of a path that no workflow reaches.
- **A checkout only where the origin is a fallback.** `fetch_pr_check_verdicts` reads the origin only when `gh pr checks` fails and it has no repository, and the PR review helper only when it has no repository. Each takes an optional `checkout`, and with none, only the repository that it gets names one. Rejected: a required `checkout`. Twenty test calls that give a repository would give a checkout that the function never reads. `resolve_branch_pr_number` requires the owner and the repository, because both of its callers give them, so its origin read was never reached.
- **One read in `devops review pr`.** The command reads `find_repo_root(Path.cwd())` one time and gives it to the PR review helper and to `_run_pr_review_workflow`, which read the working directory one time each before. From a subdirectory, the head fetch now also finds the origin of the checkout.
- **The rule holds the scanners, and a test holds the lookup.** The rule `review-cwd-read` gets two patterns: the name `DEFAULT_CURRENT_PATH`, and a parameter default of `Path(".")`. A comparison with `Path(".")`, as in `ai/review/pipeline.py`, stays valid. `core/repo.py` is outside the rule, because `find_repo_root` reads `Path.cwd()` there on purpose, so an invariant test in `tests/invariants/test_source_tree.py` holds the root parameter of `get_repo_origin_name` to no default. Rejected: one invariant test with a list of the six functions. #2098 put the construct rules in ast-grep, which the commit hook runs, and a list holds only the functions in it.

## Risks / Trade-offs

- [A command with no `--repo`, run outside a checkout on a GitHub runner, names no repository.] → No workflow does this. The command tells the user to give `--repo`.
