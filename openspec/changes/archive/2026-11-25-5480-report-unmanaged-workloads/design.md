# Design

## Decisions
- Invoke `run_subprocess(["konmon", "check", "orphaned", "-o", "json", ...], check=False, intent="read")` from `collect()` in `src/devops_cli/k8s/doctor.py` so `devops k8s doctor` keeps pure in-memory `diagnose(Snapshot(...))` deterministic while `collect()` handles live/fake PATH executables.
- Treat `konmon check orphaned -o json` output as valid findings whenever `stdout` decodes to a JSON object with a `"findings"` list and `returncode in (0, 1)` (because real `konmon` exits `1` when a named check such as `orphaned` reports findings). Treat exit `1` without valid JSON (such as `permission denied` on stderr), exit codes `> 1`, missing binary (`shutil.which("konmon") is None` or `FileNotFoundError` / exit `127` with not-found message), or invalid JSON on exit `0` as a cluster warning finding naming `konmon` and the failure text (masked via `mask_secrets`).
- Keep only `Deployment`, `StatefulSet`, `DaemonSet`, and `CronJob` entries from `konmon` findings and map each to `Finding(rule=CONST_K8S_DOCTOR_RULE_ORPHANED_WORKLOAD, severity="warning", class_="workload", resource=f"{kind}/{namespace}/{name}", ...)`, leaving cluster-wide health/skew checks unaffected.
- Add `PlannedRequest(method="konmon", target=...)` to `plan_doctor_requests()` so `--dry-run` records the read-only `konmon check orphaned` step alongside Kubernetes API reads.

## Rejected alternatives
- Build a custom `kubectl`-based orphan workload scanner in Python: rejected by the owner per `AGENTS.md` rule 3 because `guettli/konmon` already covers cluster-wide Argo CD tracking and system namespace filtering.
- Treat every `returncode != 0` from `konmon` as an error before parsing `stdout`: rejected because `konmon check orphaned` returns exit `1` specifically when orphans are present in valid `-o json` output, whereas failed executions write errors without valid findings JSON.
