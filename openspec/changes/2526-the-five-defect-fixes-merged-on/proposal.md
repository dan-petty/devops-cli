# Proposal

## Why

Issue #2526: six defect pull requests merged on 2026-10-28 and none of them records its root-cause lesson in a declared hardening surface. The audit `.github/workflows/defect-pr-hardening-audit.yml` found each one, but its intake step crashed before it filed the finding (#2524). This change writes one guardrail sentence for each defect class into the declared surface that fits it, so the class does not return.

| Pull request | Issue | Defect class | Surface |
| :--- | :--- | :--- | :--- |
| #2446 | #2106 | a scan of a lockfile rewrites the lockfile, and a scan that cannot run reads as clean | `SECURITY.md` item 7 |
| #2470 | #1632 | a chart pin that closes a CVE falls back to an affected release | `CONTRIBUTING.md` section 1 |
| #2488 | #1110 | a text that names a server keeps the userinfo of its URL | `SECURITY.md` item 1 |
| #2521 | #2431 | a host name is looked up twice, and a rebinding DNS server answers two addresses | `SECURITY.md` item 2 |
| #2522 | #1652 | a pod that does not call the Kubernetes API mounts a token | `SECURITY.md` item 5 |
| #2516 | #2426 | an audit reads a file list of its own and misses a file that the loader merges | `CONTRIBUTING.md` section 1 |

## What Changes

- `SECURITY.md` item 7 gets a sentence on a scan that reads a lockfile (#2106).
- `SECURITY.md` item 1 gets a sentence on a text that names a server (#1110).
- `SECURITY.md` item 2 gets a sentence on one lookup of a host name (#2431).
- `SECURITY.md` item 5 gets a sentence on the token of a pod (#1652).
- `CONTRIBUTING.md` section 1 gets two bullets: a pin that closes a CVE (#1632), and a loader and its audit (#2426).
- Each sentence names the defect class, the rule, and the check that holds the rule.
- The change has no spec delta and sets `skip_specs: true`. It edits documents only. No `devops` command, option or message, no manifest and no service changes. The audit reads the diff of a pull request, not the text of a surface, so a new sentence changes no output of `devops pr hardening-report` for another pull request.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `SECURITY.md`, `CONTRIBUTING.md`. No other file changes.

## Existing Code to Keep

The sentences point at checks that already exist. The change adds no check and changes none:

- `build_uv_audit_cmd` in `src/devops_cli/config/commands.py` and `tests/security/test_security_uv_audit.py` (#2106).
- `origin_label` and `authority_label` in `src/devops_cli/ai/client/models.py`, and `tests/ai/client/test_reply_server.py` (#1110).
- `vet_addresses` in `src/devops_cli/http/egress.py`, `src/devops_cli/sandbox/metrics.py`, `src/devops_cli/sandbox/models.py`, `tests/sandbox/test_sandbox_metrics.py` and `tests/commands/test_sandbox_networking.py` (#2431). Item 2 of `SECURITY.md` already names `vet_addresses` for the kept pre-flight checks: the new sentence extends that item and removes nothing.
- `tests/invariants/test_k8s_manifests.py` (`_TOKEN_EXCEPTIONS`) and the Service Account Tokens section of `k8s/README.md` (#1652).
- `test_loki_runs_the_grafana_community_chart_whose_loki_fixes_cve_2026_21729` in `tests/invariants/test_k8s_manifests.py`, and the spec `openspec/specs/loki-release-pin/spec.md` (#1632).
- `config_layer_paths` in `src/devops_cli/config/settings.py` and `tests/commands/test_config_audit_keys.py` (#2426).
- Tests that read these documents and must stay green: `tests/invariants/test_agents_md_claims.py`, `tests/docs/test_docs_inventory.py` and `tests/invariants/test_committed_addresses.py`.
- Two lines of the knowledge base stay as they are. The line on `automountServiceAccountToken` in `src/devops_cli/ai/knowledge_base/it_domains/tools/kubelinter_popeye_pluto.md` is a general kube-linter note. The lines on `uv sync --frozen` in `src/devops_cli/ai/knowledge_base/it_domains/tools/uv.md` are about installs, not about a scan. None holds a rule of this project, and none names one of the six issues.

## Acceptance

Each criterion of the issue maps to a group of `tasks.md`:

- `guardrail_per_defect`: the root-cause lesson of each of the six pull requests is in a declared surface. Group 1 writes four of them and group 2 writes two. The scenario `hardening_report_passes` is pending a person: `devops pr hardening-report --pr <number>` counts the lines that the defect pull request itself adds to a surface (`audit_pr_hardening` in `src/devops_cli/github/defect_classifier.py`). A later pull request cannot change the report of an old one, and the six stay unhardened whatever this change adds. The audit runs when a pull request closes, so it never audits them again. Task 2.3 gives the check that replaces the scenario.
- `guardrail_names_defect_class`: group 1 and group 2 write, in each sentence, the defect class, the rule and the check that holds it. Task 2.3 checks this with numbered steps.
- `guardrail_in_best_fit_surface`: each sentence is in one item or section that holds rules of the same class. Task 2.3 counts each issue number in the declared surfaces and expects one.

## Feasibility

All commands ran on `origin/main` (1c20865a) on 2026-11-01.

- The six pull requests are defect pull requests that the audit misses. `uv run devops pr hardening-report --pr 2446 -f json` (and the same for 2470, 2488, 2521, 2522 and 2516) prints `"is_defect": true`, `"reasons": ["label:type/security", "title:fix"]` and `"is_hardened": false`, with `0` for each of the eight surfaces.
- The scenario `hardening_report_passes` cannot pass for them. `git grep -n 'additions' -- src/devops_cli/github/defect_classifier.py` shows that `audit_pr_hardening` sums the `additions` of the files of the audited pull request. So the deliverable is the guardrail text, and the acceptance section says so.
- No newer work did the job. `git grep -n -i -E 'userinfo|automountServiceAccountToken|--frozen|config_layer_paths|CVE-2026' -- SECURITY.md CONTRIBUTING.md ARCHITECTURE.md docs/TESTING.md` prints nothing. The same grep over `.devops/review.toml`, `src/devops_cli/review/rules` and `src/devops_cli/ai/tasks/*.md` prints nothing. `git log origin/main --since=2026-10-28 -- SECURITY.md CONTRIBUTING.md` lists commits such as #2845 (pre-flight resolve paths) and #2492, and none adds one of the six lessons. The mechanisms below are still in the code, so no later deletion made a lesson moot.
- #2446: `sed -n 262,274p src/devops_cli/config/commands.py` shows `build_uv_audit_cmd` return `[BIN_UV, "audit", "--frozen", "--quiet", "--output-format", "json"]`. `uv audit --help` (uv 0.13.6) prints `--frozen  Audit the requirements without locking the project`. The docstring of `src/devops_cli/security/uv_audit.py` says a review does not run this adapter, because its sandbox has no network. The agent tool and the MCP tool `scan_uv_audit` run it, and item 7 of `SECURITY.md` already says that the scans of `devops scan` and of the agent tools are not reviews. So the sentence goes to the `direct` bullet of item 7, and it names uv. It does not say that every adapter takes `--frozen`.
- #1110: `git grep -n -E 'def (origin_label|authority_label)' -- src/devops_cli/ai/client/models.py` prints both functions. `git grep -n netloc -- src/devops_cli/ai/client` prints one line, in `authority_label`, which builds the text from a host and a port and holds no userinfo.
- #2431: `git grep -n vet_addresses -- src/devops_cli/sandbox` prints the calls in `_resolve_public_dns` and `_resolve_local_dns` of `src/devops_cli/sandbox/models.py`. `git grep -n -E 'getaddrinfo|validate_url_egress' -- src/devops_cli/sandbox` prints nothing. The lookup happens when the NetworkPolicy is built, and when the scrape connects. So the sentence says "one lookup" and does not say "at connect time" for both.
- #1652: `git grep -l 'automountServiceAccountToken: false' -- k8s` lists 21 files. `git grep -n -E '_TOKEN_EXCEPTIONS|def test_the_pods_that_do_not_call_the_api_mount_no_token' -- tests/invariants/test_k8s_manifests.py` prints the table and the test.
- #1632: `git grep -n -E 'repoURL|chart:|targetRevision' -- k8s/argocd/apps/loki.yaml` prints `https://grafana-community.github.io/helm-charts`, `loki` and `20.0.2`. `git grep -n 'def test_loki_runs' -- tests/invariants/test_k8s_manifests.py` prints the invariant test. `CONTRIBUTING.md` has no dependency section: `git grep -n -i -E 'CVE|chart' -- CONTRIBUTING.md` prints nothing. Section 1 (Development Philosophy and Core Invariants) is the list of rules for every contributor, and it holds the bullets on tests and tables. A bullet on a pin that a test holds fits there.
- #2426: `git grep -n config_layer_paths -- src` prints the definition in `src/devops_cli/config/settings.py`, the use in `_config_layers` (which `load_settings` reads) and the use in `audit_keys_cmd` of `src/devops_cli/commands/config.py`. `git grep -n 'def test_config_audit_keys_fails_on_a_plaintext_secret_in_the_global_config_file' -- tests` prints the test.
- Each path in this change exists on `origin/main`: a script tested each code span against `git ls-tree -r origin/main`.

## Existing Tool Considered

No open, maintained tool or library writes the guardrails of a project into its own documents. The audit workflow only detects a missing guardrail. The change builds nothing and deletes no code. The cost is the tokens to write six sentences and to keep them true when a check changes, and the time of a person to read the diff.
