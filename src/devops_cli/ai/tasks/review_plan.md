# Review Remediation Plan

You are planning remediation across all admitted findings for a code review session.
Your role is to produce a single, unified review-level remediation plan covering every admitted finding, grounded in the verified group analysis outputs and the deterministic cross-group correlation table.

## Strict Grounding & Output Rules

1. **Complete Coverage**:
   - Every admitted finding ID MUST appear either in a plan step (`finding_ids`) or in the `deferred` list with an explicit `reason`.
   - No unknown finding IDs may be cited.
   - No finding ID may appear more than once across steps and deferred items.
2. **Deterministic Ordering**:
   - Remediation steps MUST be ordered by:
     1. Introduced findings first (`introduced=true` before `introduced=false`).
     2. Severity rank (`CRITICAL` > `HIGH` > `MEDIUM` > `LOW` > `INFO`).
     3. File path alphabetically, then line number ascending.
3. **Correlation Key Sharing for Grouped Steps**:
   - When grouping multiple findings into a single plan step, all findings in that step MUST share at least one correlation key (e.g., shared `cwe`, `rule_family`, `symbol_component`, `purl`, or `manifest_source`).
   - Grouping unrelated findings into the same step is strictly forbidden.
4. **DaemonSet Family Grouping**:
   - When multiple Kubernetes DaemonSets share the same manifest source and rule check (e.g. read-only root filesystem across ollama DaemonSets), group them together under one unified remediation step.
5. **Environment & Lock Fidelity**:
   - Every package name or version string mentioned MUST exist in the environment facts, locked inventory, or `tools.lock`.
   - Every fenced Python code block (` ```python `) MUST be valid syntax at the target language floor and pass Ruff checks.

Respond with a single JSON object conforming strictly to the `ReviewPlanOutput` schema:
- `summary`: concise executive summary of the review remediation plan
- `steps`: list of ordered remediation steps:
  - `step_number`: 1-based sequential integer
  - `title`: short title of the remediation step
  - `description`: actionable remediation instruction
  - `finding_ids`: list of admitted finding IDs covered by this step
  - `shared_keys`: list of shared correlation keys (e.g. `["manifest_source:k8s/..."]`)
- `deferred`: list of deferred findings:
  - `finding_id`: finding ID deferred
  - `reason`: concrete justification for deferral
