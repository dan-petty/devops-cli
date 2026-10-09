# Task: kube-linter findings carry their own check, message and manifest file, and scan reports keep each one (#1045)

**Issue**: [#1045](https://github.com/dan-petty/devops-cli/issues/1045)
**Status**: Done
**Milestone**: v0.2.30
**Priority**: priority/p2-medium
**Scope**: type/bug, scope/security, scope/review

## Description

kube-linter writes `Check` and `Remediation` beside `Diagnostic`, which holds only `Message`. `_finding_from_report` (`src/devops_cli/security/kubelinter.py`) read the check from `Diagnostic`, so every kube-linter finding since v0.1.8 was titled `[kube-linter-check] K8s Security Lint Warning`, and its fix said "to resolve kube-linter-check". `parse_kubelinter_json` ignored `Object.Metadata.FilePath`, so a directory scan located every finding at the directory. The fingerprint (tool, rule id, path, canonical message) was then the same for every kube-linter finding of a scan, and `devops scan report` kept 1 of the 7 reports over `k8s/` at da50329. A review merged the reports on one object into one candidate (D12 in the S10 comment).

**The adapter.** A finding is titled `[<check>] <message>`, the form the Bandit and Semgrep adapters write, so the check is the rule id and SARIF `ruleId`. The fix is kube-linter's `Remediation`, or the template when a report has none. The location is `<manifest>:<symbol>`: the manifest is `FilePath`, made relative as `_manifest_location` does, and `target_path` only when `FilePath` is missing; the symbol is `Kind/<namespace>/<name>`, or `Kind/name` when kube-linter reports `Namespace: ""`. No namespace is guessed: the `default` the adapter used to write is gone. The description is `<message> for <Kind> '<name>'.`. `Check` and `Diagnostic.Message` are read strictly, since kube-linter 0.8.3 always writes both; no `kube-linter-check` sentinel is left.

**The category.** `_category` takes the first class that `defect_class` finds in the check name, then the message, that is neither `other` nor `security`, and otherwise `security_misconfiguration`: kube-linter checks manifests for misconfiguration. Over the fixture, `no-anti-affinity` is `reliability` (the word "affinity") and the other three checks are `security_misconfiguration`.

**The identity** (`src/devops_cli/security/normalization.py`).
- `NormalizedFinding.fingerprint` hashes the symbol after tool, rule id, path and canonical message, only when there is one. A finding without a symbol keeps its fingerprint; `make().fingerprint == "628a47241e8969b848c97efe8db7637c"` is pinned at the base commit. The line stays out: an object's name, unlike a line, does not move when lines are added above it. `CONST_SARIF_FINGERPRINT_KEY` stays `devopsCli/v1`, because #855 has not landed.
- `split_location` reads a line or line range with `ai.review_schema._parse_location`, the parser `ai/review/pipeline._parse_candidate_location` already pairs it with, before taking a non-numeric suffix as the symbol. Without this, the symbol in the fingerprint would have put lines into it: Semgrep writes a multi-line result as `path:start-end`, which was read as the symbol `40-45`, and checkov, tflint and kubeconform write `:<line>` when they have no path, which was read as the symbol `1`. Both now read as their start line, so they keep their fingerprints when they move. The `suffix.isdigit()` branch this made unreachable is removed.
- `NormalizedFinding.correlation_key` is `(path, line, symbol, canonical message)`. `devops scan report` renders clusters, not findings, so without the symbol the `prometheus` and `kube-prometheus-kube-prome-prometheus` Services, which share one message, were one row naming one object. Each `--json` cluster entry carries the representative's `symbol`, as each finding entry does, so those two rows are not identical objects.

**The table.** `format_k8s_lint_table` (`src/devops_cli/output/formatters/tables.py`), which `devops k8s lint` prints, escapes its location, title and fix cells with `escape_text`, as `format_review_findings_table` does. Rich otherwise reads the title's `[no-anti-affinity]` as a markup tag and drops it, so no column named the check.

**The symbol form.** `Kind/<namespace>/<name>` follows Kubernetes' `namespace/name` object key (client-go's `MetaNamespaceKeyFunc`, which writes `name` alone for an object with no namespace), prefixed by the kind, and is the form Popeye's locations already have (`<sanitizer>/<namespace>/<name>`). The no-namespace form `Kind/name` is recorded here for #1352's shared key function.

## Acceptance Criteria

- [x] `_finding_from_report` reads `Check` and `Remediation` from the report and `Message` from `Diagnostic`. The title is `[<check>] <message>`, and the fix is the `Remediation`, or the template without one (`test_each_title_names_its_own_check_and_message`, `test_the_fix_is_kube_linters_remediation`, `test_a_report_without_a_remediation_gets_the_template_fix` in `tests/test_security_kubelinter.py`).
- [x] The category is the class the check name or the message names, and `security_misconfiguration` when neither names one or they name only `security` (`test_the_category_is_the_class_the_check_names_or_a_misconfiguration`).
- [x] The location names the manifest from `Object.Metadata.FilePath`, made relative as `_manifest_location` does; `target_path` is used only when `FilePath` is missing, and a directory scan names each file (`test_each_location_names_its_own_file_and_object`; `test_kubelinter_locations_are_relative_to_the_nested_worktree` in `tests/test_secops.py` covers a report without `FilePath`).
- [x] `NormalizedFinding.fingerprint` includes the symbol when the finding has one, a finding without a symbol keeps its fingerprint, and the line stays out (`test_a_fingerprint_distinguishes_two_objects_with_one_message`, `test_a_finding_without_a_symbol_keeps_its_fingerprint`, `test_a_fingerprint_survives_the_finding_moving_to_a_new_line` and `test_a_multi_line_result_keeps_its_fingerprint_when_it_moves` in `tests/test_security_sarif.py`).
- [x] Two Popeye issues on two resources of one sanitizer go through `build_report` and both are kept; the base code kept 1 (`test_two_popeye_issues_on_two_resources_of_one_sanitizer_are_kept`).
- [x] The fixtures of `test_kubelinter_parser` and `test_kubelinter_scanner_execution` put `Check` at report level (the second also puts `Kind` under `GroupVersionKind`). `tests/fixtures/kubelinter/k8s-da50329.json` holds the 7 reports of `kube-linter lint k8s --format json` at da50329 (kube-linter 0.8.3, 4 checks, 3 files), trimmed to `Check`, `Diagnostic.Message`, `Remediation`, `Object.Metadata.FilePath` (made relative) and `Object.K8sObject`, plus `Summary.KubeLinterVersion`. `tests/test_security_kubelinter.py` parses it; each test failed on the base code.
- [x] The fixture through `build_report` keeps 7 of 7 findings in 7 clusters, whose 7 `--json` entries are distinct, under the rule ids `dangling-service`, `no-anti-affinity`, `no-read-only-root-fs` and `run-as-non-root`, and `to_sarif` declares those 4 rules; the base code kept 1 under 1 rule (`test_a_scan_report_keeps_every_finding_under_its_own_rule`).
- [x] `devops k8s lint` prints the check in its Title column: a finding titled `[no-anti-affinity] ...` renders with `[no-anti-affinity]` (`test_the_kube_linter_table_names_each_check` in `tests/test_output.py`; it failed before the cells were escaped).
- [x] The kube-linter contract sample's title names `no-read-only-root-fs` (`test_kubelinter_contract_finding_names_its_check` in `tests/test_consolidation_security_scanner_base.py`, beside the parametrized contract test).
- [x] The tests run offline, call no kube-linter binary, and each runs well under 1 s.
- [x] `changelog.d/1045.md` records the fix under `### Fixed`, including the one-time fingerprint change of every symbol-located finding (Trivy, Pluto, Popeye, Dive, kube-linter). `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
- [x] From the 2026-10-03 additions: the check name is the SARIF `ruleId`, and kube-linter's symbol is `Kind/<namespace>/<name>`, or `Kind/name` without a namespace.
- [x] From the S10 comment: `consolidate_duplicate_findings` keeps the 7 fixture findings; the base code kept 6, because the registry Deployment's two checks merged (`test_a_review_keeps_two_checks_on_one_object`).
- Pending a person: `devops scan report k8s --scanner kubelinter` shows one row per kube-linter report under its own check: 7 rows under 4 rule ids over da50329's `k8s/`, 6 under 4 over the release head's `k8s/` (the pyroscope alias is gone). An agent run on this branch with kube-linter 0.8.3 gave 6 findings in 6 distinct `--json` clusters, each naming its object.
- Pending a person: `devops k8s lint k8s/cloudflared/deployment.yaml` names `no-anti-affinity`. An agent run on this branch with kube-linter 0.8.3 showed `[no-anti-affinity] object has 2 replicas ...` in the Title column.

## Re-scope (issue update of 2026-10-09)

- "kube-linter runs once over the manifest set, with a per-file status": dropped. kube-linter 0.8.3 gives no per-file status from one run: a file that fails to load shows up only as a `-v` stderr warning, the exit code and JSON match a clean run with findings, and a run over only unloadable files exits 0 with no output. Parsing that log text by hand is ruled out. Running once does not remove the false `dangling-service` rows either: one run over `k8s/` at da50329 still reports 4 on `k8s/monitoring/service-aliases.yaml`, whose Services select Helm-deployed pods; #1024 drops the check from the review config.
- Pluto's object form: moved to #1434. Its parser reads `kind` and `filepath`, but Pluto writes `api.kind` and `filePath`, so a namespace alone would give `Resource/<namespace>/<name>`.
- Trivy and Dive identity: moved to #1141 (`purl@version` for advisories, the image for Dive); they are not Kubernetes objects.
- Popeye needs nothing more than the fingerprint change: its location already has the `<sanitizer>/<namespace>/<name>` shape.

## Deliverables

- [x] `src/devops_cli/security/kubelinter.py`: `_finding_from_report` reads the report's own check, message, remediation, file and object; `_category`; `_reported_object` guesses no namespace.
- [x] `src/devops_cli/security/normalization.py`: `split_location` reads a line or range through `_parse_location`; `fingerprint` hashes the symbol when there is one; `correlation_key`, `FindingCluster.key` and `correlate` carry the symbol.
- [x] `src/devops_cli/security/pipeline.py`: `ScanReport.as_dict` writes each cluster's `symbol`.
- [x] `src/devops_cli/output/formatters/tables.py`: `format_k8s_lint_table` escapes its location, title and fix cells; `tests/test_output.py` renders one.
- [x] `tests/fixtures/kubelinter/k8s-da50329.json` and `tests/test_security_kubelinter.py`.
- [x] `tests/test_security_sarif.py`: the fingerprint, location, Popeye and correlation tests above; the `:1` case reads as line 1.
- [x] `tests/test_secops.py`, `tests/test_consolidation_security_scanner_base.py` and `tests/test_common_hallucinations_hardening.py`: the real kube-linter report shape and title.
- [x] `docs/agent/tasks/task-321-security-scanners-unified-sarif-engine-cross-tool-deduplicat.md` (identity, location shapes and clusters), `docs/agent/tasks/task-972-reviews-take-nothing-from-the-tree-under-review.md` (its known limit about `kube-linter-check` titles is gone) and `docs/SELF_IMPROVEMENT.md` (the kube-linter object form).
- [x] `changelog.d/1045.md`.

## Risks and Notes

- Every symbol-located finding gets a new fingerprint and SARIF `partialFingerprints` value once, so a fingerprint suppression of one must be recorded again. A suppression by rule `kube-linter-check`, in a scan policy or `.devops/review.toml`, must name the check. The project is pre-1.0, so the changelog fragment is the record and no migration is added.
- A `path:start-end` location now displays as `path:start` in `devops scan report`, and SARIF gives it a region at its start line in place of a logical location named by the range.
- A finding with neither a `FilePath` nor a target is written `:<symbol>`, which `Finding`'s location validator turns into `<symbol>`, read as a path. The old form ended the same way, and no scanner run produces it.
- #1138 parses saved review sessions by kube-linter check, path and object: sessions made before this change have `Kind/name` and the template title, later ones `Kind/<namespace>/<name>` and the check, so its parser must accept both.
- #1024: this change gives each object its own identity and resolves no object across files, so `dangling-service` stays excluded from the review config.
- #1141 and #855 rebase on the new `split_location`, `fingerprint` and `correlation_key`; #1352 and #1434 write the same `Kind/<namespace>/<name>` form.
