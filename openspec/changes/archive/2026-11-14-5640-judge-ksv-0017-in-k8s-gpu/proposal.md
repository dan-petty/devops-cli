# Proposal

## Why

The Security Scan reports KSV-0017 at HIGH for the GPU feature discovery DaemonSet, and issue #5640 asks for the judgment that SECURITY.md names. The container keeps `privileged: true` for GPU device and sysfs access, so the manifest change is deferred to #5646 and the alert needs a dated ignore entry.

## What Changes

- Create `.trivyignore.yaml` with one `misconfigurations` entry for the rule `KSV-0017` on the path of the GPU feature discovery DaemonSet.
- Give the entry a `statement` that names the privileged GPU device and sysfs access of the workload and the tracking issue #5646.
- Set `expired_at` to the day of the commit plus 3 days, the agent limit of SECURITY.md.
- Add `test_the_repository_ignore_file_holds_the_privileged_gpu_entry` to `tests/security/test_trivy_config_ignore.py`; it finds the entry among the entries of the file and asserts its rule, its path, its statement and its expiry date.
- Keep the GPU feature discovery DaemonSet out of the diff, because #5646 delivers the manifest change.
- Add a requirement to `trivy-config-alerts` for the dated entry, because the ignore file changes what the Security Scan reports.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `trivy-config-alerts`: The privileged GPU workload holds a dated ignore entry

## Impact

- Code: `.trivyignore.yaml`
- Tests: `tests/security/test_trivy_config_ignore.py`

## Feasibility

- The premise of the issue is that Trivy reports KSV-0017 for the cited manifest, and the probe of that path reads, word for word: The path `k8s/gpu-feature-discovery/daemonset.yaml` is a file of the staging commit.
- The probe of the policy reads, word for word: The path `SECURITY.md` is a file of the staging commit.
- The probe of the ignore file reads, word for word: The path `.trivyignore.yaml` is no file of the staging commit. No commit in the history deleted or renamed it. So the plan creates the file that the issue asks for, and no commit removed it.
- The probe of the expiry field reads, word for word: `expired_at` has no definition at the staging commit. It is a field of the new YAML file and no Python symbol, so the plan defines no code symbol for it.
- The probe of the statement field reads, word for word: Not probed, the bound of 10 commands is reached: `statement`.
- `read_file` of `SECURITY.md` lines 75 to 125 showed the section `Judging a Trivy-config Alert` and the rule for the YAML entry: `SECURITY.md:105:If the fix breaks the workload` — the entry takes the rule id, the paths, a statement with the tracking issue and an `expired_at` date.
- `SECURITY.md:101:An agent judges an alert of severity HIGH, MEDIUM or LOW within 14 days.` — an agent judges this HIGH alert, so no owner decision is needed.
- `SECURITY.md:88:Ignore a finding of severity CRITICAL. Ask the owner.` — this HIGH alert is below that line, so an agent may ignore it for a time.
- `SECURITY.md:106:A person dismisses the alert in code scanning, with a reason. An agent does not dismiss an alert.` — so the plan takes the ignore entry and not a dismissal.
- `search_code` for `privileged: true` returned `k8s/gpu-feature-discovery/daemonset.yaml:59:privileged: true` — the container that the alert names runs privileged.
- `search_code` for `CONST_TRIVY_CONFIG_IGNORE_FILE` returned `src/devops_cli/config/constants.py:5072:CONST_TRIVY_CONFIG_IGNORE_FILE: Final[str] = ".trivyignore.yaml"` and `src/devops_cli/security/trivy.py:243:ignore = Path(cwd) / CONST_TRIVY_CONFIG_IGNORE_FILE if cwd else None`.
- `file_symbols` of `src/devops_cli/security/trivy.py` lists `src/devops_cli/security/trivy.py:class TrivyConfigScanner` at line 223 with `build_command` at line 231, so the IaC scan reads the file of the scan directory and no code changes.
- `read_file` of `tests/security/test_trivy_config_ignore.py` showed three tests of that scanner, so the new test joins an existing module of the folder that mirrors the package.
- `read_file` of `.trivyignore` showed `line 7` holding `Trivy has no path field in this file format, so the entry`, so the plain file cannot scope the rule to one path and the plan uses the YAML form.
- `search_code` for `scan report --sarif` returned `.github/workflows/ci.yml:99:run: uv run devops scan report --sarif .data/scan.sarif --skip bandit,trivy` — the Security Scan step runs the trivy-config scanner, and `--skip trivy` skips only the filesystem scanner.
- `read_issue` of #5646 showed it open with the title `fix(security): remove privileged mode from gpu-feature-discovery`, split from #5640, so the statement names a live tracking issue.
- `find_issues` with `trivyignore.yaml KSV-0017` listed 4 open items: #5640, #5371, #5642 and #4409. #5371 judges the same rule on the same path, so it is a duplicate whose entry is the same entry, and #5642 judges another rule of the same file, so the test accepts other entries.
- The previous reply named the DaemonSet path in What Changes with no group that changes it; this plan names no path in What Changes for the unchanged file, and the DaemonSet appears only in `reads` and in the citation of the probe.
- The new test guards the set of `misconfigurations` entries of `.trivyignore.yaml`: the count at the staged tree is zero, because the probe shows that the file does not exist; the change writes one entry, and the test allowlists each other entry with the reason that another judged alert owns it.
- `yaml.safe_load` and `Path.read_text` in the new test need a checkout of the repository: they read `.trivyignore.yaml` at the root of the working tree.
- The verify `uv run devops ci test tests/security/test_trivy_config_ignore.py` needs a checkout of the repository, and no client of a service and no network.
- The verify starts `uv`, `python`, `pytest` and `devops` from the runner image; `trivy` is `NOT_IN_RUNNER`, so no scan runs in the step, and the pod runs the step as non-root with a read-only root filesystem, no privilege escalation, all capabilities dropped and the `RuntimeDefault` seccomp profile.
- The verify can stop only with the class of a failed test; it needs no network, cluster or scanner failure class, and it writes no file outside the pytest temporary folder.
- The first check of the implementation is `uv run devops ci test tests/security/test_trivy_config_ignore.py`. The real IaC scan is `uv run devops scan report --sarif .data/scan.sarif`, which runs on a host that holds Trivy because the runner image holds none.
- The plan builds no code, so `builds_own` is false and the ignore file is the tool's own format.

## Existing Tool Considered

Trivy's `.trivyignore.yaml` ignore file covers the need: Trivy config is the pinned, maintained scanner, `TrivyConfigScanner` names that file with `--ignorefile`, and an entry takes the rule, the paths, a statement and an expiry date, so the change adopts it and builds no code.

## Dependencies

None.
