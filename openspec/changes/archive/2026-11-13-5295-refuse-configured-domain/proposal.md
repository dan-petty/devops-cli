# Proposal: #5295

## Why
After step 14 of the homelab migration plan (#5120), the real hosts are in homelab files at the same paths as the devops-cli files, and agents copy text between the two trees. The guard `tests/invariants/test_committed_addresses.py` refuses RFC 1918 addresses and `.lan` hosts only. No check reads `k8s.domain` or `cloudflare.domain`. So a commit that names the configured public domain passes each check and can go into the public repository. Closes #5295.

## What Changes
- A new row `domain` of `devops ci` (`tests/gate/configured_domain.py`). It reads `k8s.domain` and `cloudflare.domain` from the config at run time. It reads the patch of each commit from `origin/main` to `HEAD` with `git log -p`, and `unidiff` gives the path and the line number of each added line. The row fails on each added line or path that holds a configured domain, in any case, with no letter, digit or hyphen just before or just after it. So `api.example.net` and `grafana.example.net.yaml` name `example.net`, and `notexample.net` does not. It names the file, the line, the commit and the setting, and it never prints the value. A path that names a domain is not printed: the row names the commit.
- When no domain is configured, the row starts no command, passes, and shows `skipped: <cause>`, which says that it read no commit.
- The pre-push hook `devops-ci-pre-push` runs `devops ci --check --only lint,format,domain`. So each push of a person, an agent or the runner Job reads the commits of the branch before they go to GitHub.
- `devops_cli.core.dns_names.configured_domains` gives the configured domains by settings key, for the row and for the skip check of `devops ci`.
- SECURITY.md rule 8 says how the row works and says that public evidence, such as a pull request comment, holds exit codes and counts only, never `argocd app diff` output or Application YAML.
- The row is a behavior that a person sees in the output of `devops ci`, so the change has a delta of the capability `ci-gate-rows`.

The change fits one pull request.

## Capabilities
- `ci-gate-rows` (modified): ADDED requirements "The domain row refuses a commit that names a configured domain", "The domain row never prints the value of a domain", "The domain row is skipped where no domain is configured" and "The pre-push hook runs the domain row".

## Impact
- `devops ci` and the pre-push hook have one more row. Where no domain is configured (the GitHub runners, a new workstation), the row is skipped with its cause. The row reads only the commits of the branch, so a name that `main` holds already does not fail it.
- No value of a domain goes into git: the tests use `example.net` as the configured domain in their own config and `example.com` as a name that passes.
- Rollback: `git revert`. No downtime.

## Feasibility
- The settings exist on `origin/main`: `KubernetesConfig.domain` and `CloudflareConfig.domain` in `src/devops_cli/config/settings.py`, both `OptionalConfiguredDomain`. `uv run python -c` with `load_settings()` on the workstation of the owner showed that both are set (the probe printed booleans only, never the value).
- No guard reads them: `git grep -n "k8s.domain\|cloudflare.domain" origin/main -- tests .pre-commit-config.yaml` names no check.
- `git log -p -U0 --format=%x00%H origin/main..HEAD` (git 2.55.0) gives one NUL-separated record for each commit, and `unidiff` 1.0.1 (a pinned dependency, `pyproject.toml`) parsed each record of a scratch repository into `PatchedFile` objects with `target_line_no` for each added line.
- A probe with the real config of the owner made a scratch repository outside the worktree with two commits: one adds a host under the configured domain in upper case, and one adds `example.com` only. The check gave exit status 1 and one finding, `a.yaml:1 in commit <sha> names the value of k8s.domain`, and its output did not hold the value. The probe printed counts and that finding only, and removed the repository.
- The set that the guard reads is the commits from `origin/main` to `HEAD` of the pushed branch. `uv run devops ci --check --only domain` on this branch before its first commit read 0 commits and passed.

## Existing Tool Considered
- Gitleaks (pinned in `tools.lock`, installed in the devcontainer, adapter `devops_cli.security.gitleaks`) can refuse a pattern with a custom rule that the check writes at run time to a temporary file, and `gitleaks git --log-opts=<range> --redact` names the file and the line. It is not used here, for two reasons that the design records: the runner image keeps it out (`NOT_IN_RUNNER` in `src/devops_cli/roadmap/runner_tools.py`) and the Static Analysis job installs no scanner, so the runner Job would drop the hook and push with no check; and the test floor refuses a real scanner (docs/TESTING.md), so no test could show that the rule matches a configured domain.
- git and unidiff cover the need instead. Gitleaks itself reads `git log -p -U0` and parses it with a diff library. git gives the added lines of each commit, `unidiff` parses them, and the standard `re` module finds the escaped domain with a bound on each side, which is the pattern that a Gitleaks custom rule would hold. The new code is the glue: the read of the two settings, the match of each added line and the output.
- Cost to build: about 0.3M tokens to build, 0.05M tokens a quarter to keep and fix, and 2 hours.
- Internal code that the change deletes: none.
