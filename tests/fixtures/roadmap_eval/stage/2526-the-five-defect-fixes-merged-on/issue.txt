### Problem Description

Five defect pull requests that merged on 2026-10-28 add no guardrail or lesson to a declared hardening surface. The audit `.github/workflows/defect-pr-hardening-audit.yml` (`devops pr hardening-report`) found each one, but its intake step crashed before it filed the finding (#2524: the `ZeroDivisionError` in the embedder). This issue holds the five findings in one item, because they have one cause and one change surface.

| PR | Issue | Change |
| :--- | :--- | :--- |
| #2446 | #2106 | `scan_uv_audit` runs one `uv audit --frozen` adapter |
| #2470 | #1632 | Loki runs from the grafana-community chart on Loki 3.7.9 (CVE-2026-21729) |
| #2488 | #1110 | a reply names its server by the origin of the URL called, with no userinfo |
| #2521 | #2431 | the sandbox metrics scrape and the whitelist NetworkPolicy resolve each host one time, through the egress check |
| #2522 | #1652 | a pod that does not call the Kubernetes API mounts no service account token |

The declared hardening surfaces are `docs/TESTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, `CONTRIBUTING.md`, `src/devops_cli/ai/tasks/*.md`, `src/devops_cli/ai/knowledge_base/`, `.devops/review.toml` and `src/devops_cli/review/rules/`.

### Reproduction Steps

1. Run `uv run devops pr hardening-report` for each PR in the table (read its `--help`).
2. See that each PR is reported as unhardened.

### Expected vs Actual Behavior

Expected: each defect fix adds its root-cause lesson to at least one declared surface, for example a `SECURITY.md` rule for the egress check of every client, a review rule for userinfo in a display string, or a `docs/TESTING.md` rule, so that the defect class does not return.

Actual: the five PRs changed code, tests and other documents only.

### Environment Diagnostics

`main` at 2026-10-28.

### Logs, Traces, or Terminal Output

Audit runs 40726982400, 40739487773, 40747696823, 40758319104 and 40758364472 (step "Audit defect PR hardening" failed, then the intake step crashed).


Source: https://github.com/dan-petty/devops-cli/actions/workflows/defect-pr-hardening-audit.yml

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
Six defect pull requests merged on 2026-10-28 changed code, tests and documents, but none added its root-cause lesson to a declared hardening surface. The audit found each one, but its intake step crashed before it filed the finding. This issue holds the six findings in one item because they share one cause and one change surface. The change adds a guardrail for each defect class to the declared surface that best fits it, so the defect class does not return.

### Acceptance criteria

### Requirement: guardrail_per_defect
Each of the six defect PRs SHALL have its root-cause lesson recorded in at least one declared hardening surface.

#### Scenario: hardening_report_passes
- **WHEN** devops pr hardening-report runs for each of the six PRs (#2446, #2470, #2488, #2521, #2522, #2516)
- **THEN** each PR is reported as hardened, not unhardened

### Requirement: guardrail_names_defect_class
Each guardrail entry SHALL name the defect class it prevents and the rule that prevents it.

#### Scenario: guardrail_text_is_specific
- **WHEN** a reviewer reads each guardrail entry in its surface
- **THEN** the entry names the defect class, the prevention rule, and the surface where it is enforced

### Requirement: guardrail_in_best_fit_surface
Each guardrail SHALL appear in the declared surface that best fits its defect class, not in every surface.

#### Scenario: single_surface_per_guardrail
- **WHEN** a guardrail is added to a surface
- **THEN** it appears in exactly one declared surface, and that surface has existing content that the guardrail extends

### Existing Tool Considered
No open, maintained tool or library covers this need. The project writes its own guardrail text into its declared surfaces. The cost is the tokens to write, keep and fix six guardrail entries across the declared surfaces, and the elapsed time for a person to review each entry.

### Key questions
- **Which declared surface receives the guardrail for each of the six defect PRs?**: Each guardrail goes to the surface that best fits its defect class. #2446 goes to SECURITY.md item 7 (tool execution). #2470 goes to CONTRIBUTING.md (dependency management). #2488 goes to SECURITY.md item 1 (zero secret leakage). #2521 goes to SECURITY.md item 2 (SSRF protection). #2522 goes to SECURITY.md item 5 (least privilege). #2516 goes to CONTRIBUTING.md (config management). (best practice) [sources: SECURITY.md, CONTRIBUTING.md, .github/workflows/defect-pr-hardening-audit.yml]
  - Rejected: All six to SECURITY.md. Three fit better in CONTRIBUTING.md because they are process and dependency rules, not security rules.
  - Chosen: Best-fit surface per defect class. Each surface has existing content that the guardrail extends, and the defect class matches the surface scope.
  - Rejected: All six as Semgrep rules in src/devops_cli/review/rules/. The defects are architectural and process lessons, not code patterns that a rule can express.
- **Should any guardrail be a Semgrep rule in src/devops_cli/review/rules/?**: No. The six defect classes are architectural and process lessons. None is a code pattern that a Semgrep rule can express. They are prose rules in the declared surfaces. (best practice) [sources: SECURITY.md, CONTRIBUTING.md, .devops/review.toml]
  - Rejected: Semgrep rules for all six. The defects are process and architecture lessons, not code patterns.
  - Chosen: Prose in declared surfaces. The declared surfaces already hold prose rules for similar defect classes.
- **Does the change require a code change under src/?**: No. The change adds text to existing documents. It changes no source file under src/. The declared surfaces are all documents, configuration or rules. [sources: SECURITY.md, CONTRIBUTING.md, docs/TESTING.md, ARCHITECTURE.md, .devops/review.toml]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "7158668f9ac1b767265c784f0f19f4cee838a367f3779fcb8fd00141d569afa7", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "820c1f046592fafbcacd91897207e53849ef53140f0f58ce7d7cc441047ea4a1", "stage.branch": "fix/2526-the-five-defect-fixes-merged-on", "stage.file_cap": null, "stage.groups": "[[\"Add four guardrails to SECURITY.md\", 3798], [\"Add one guardrail to CONTRIBUTING.md\", 3561]]", "stage.needs_split": null, "stage.pr": "2994", "stage.ready": "2994", "stage.sha": "208659d58c19aac5e61093c7ca3a86f061f8313a"} -->
