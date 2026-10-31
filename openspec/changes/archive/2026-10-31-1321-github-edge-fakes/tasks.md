# Tasks: Migrate github/ Tests to Edge Fakes

## 1. Test Files Migration
- [x] 1.1 Migrate `tests/test_github_secrets.py` to `process_fake` and `keyring_store`
- [x] 1.2 Migrate `tests/test_github_ssh.py` and remove private imports
- [x] 1.3 Migrate `tests/test_github_issues.py` to `process_fake` and `github_api`
- [x] 1.4 Migrate `tests/test_github_pages.py` to `process_fake` and `github_api`
- [x] 1.5 Migrate `tests/test_gh_issues_milestones.py` to `process_fake`
- [x] 1.6 Migrate `tests/test_github_client.py` and `tests/test_github_session.py` to edge fakes
- [x] 1.7 Migrate `tests/test_github_metrics.py` to `process_fake`
- [x] 1.8 Migrate `tests/test_github_branch_protection.py` to `process_fake` and `github_api`
- [x] 1.9 Migrate `tests/test_github_pr_threads.py` and `tests/test_pr_check_verdict.py` to edge fakes
- [x] 1.10 Migrate `tests/test_gh_project_workflows.py` to `process_fake`
- [x] 1.11 Migrate `tests/test_github_projects_reconcile.py` and `tests/test_github_projects.py` to edge fakes
- [x] 1.12 Migrate `tests/test_github_rate_limiter.py` to edge fakes
- [x] 1.13 Migrate `tests/test_github_pr_monitor.py` to edge fakes

## 2. Invariants and Quality Gate
- [x] 2.1 Verify zero internal patches and zero private imports in migrated test files
- [x] 2.2 Verify test names conform to ASD-STE100 and do not end in `_success`, `_failure`, `_basic`, or `_command`
- [x] 2.3 Run `uv run devops openspec check` and full `uv run devops ci`
