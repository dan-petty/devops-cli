# Proposal

## Why

A plan can rest on a false premise that only a command run shows: 8 of 48 findings in the first five plan fixes, such as a dry run of `config unset` that deleted a key (#3218). The planner reads files and runs no command, so this change writes the decision record for a sandboxed read-only run tool and the follow-up work that builds it (#3242).

## What Changes

- Add `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` with the status, the decision, the allow-list, the seven isolation controls, the run location, the output rules and the input of the owner decision on #2695.
- Add the comparison of bubblewrap, nsjail, gVisor and the agent-sandbox controller of kubernetes-sigs, the rejected options, the three proof tests and the follow-up work to the same record.
- Keep the change to documents only, so it carries no spec delta: the run tool, its Job manifest and its tests come in follow-up items, and no behavior that a consumer observes changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md`

## Feasibility

- The probes confirm each cited file: The path `SECURITY.md` is a file of the staging commit. The path `src/devops_cli/roadmap/run.py` is a file of the staging commit. The path `k8s/devops/roadmap-service/deployment.yaml` is a file of the staging commit. The path `src/devops_cli/roadmap/runner_tools.py` is a file of the staging commit. The path `src/devops_cli/ai/mcp/generator.py` is a file of the staging commit. The path `CONTEXT.md` is a file of the staging commit.
- The probe answer also shows that the proof test module of the refined design is no file of the staging commit: No commit in the history deleted or renamed it. It is a file that a follow-up creates, so the premise holds, and this change creates no test and no tool.
- `read_file` on `src/devops_cli/roadmap/runner_tools.py` lines 200-240 shows that the line number of the issue moved and that its claim holds: `src/devops_cli/roadmap/runner_tools.py:226:"gh-dash": _NO_GATE_STEP,` holds another entry of the table, and the `bwrap` entry sits further down, so the runner image leaves bubblewrap out.
- `read_file` on `k8s/devops/roadmap-service/deployment.yaml` shows the controls that the record requires: `k8s/devops/roadmap-service/deployment.yaml:41:automountServiceAccountToken: false` and `k8s/devops/roadmap-service/deployment.yaml:47:seccompProfile:`.
- `file_symbols` on `src/devops_cli/roadmap/run.py` lists `src/devops_cli/roadmap/run.py:def _run_stage_adapter`, which calls `plan_stage` in the Service process, so the planner runs in the Service pod and no stage Job exists.
- `search_code` for `CONST_MCP_EXPOSURE_TABLE` found the table in `src/devops_cli/config/constants.py`, and `src/devops_cli/ai/mcp/roles.py:def tools_for_role` keeps a tool of a job role only when the table marks it read-only, so the allow-list has a tested source.
- `search_code` for `def mask_secrets` found `src/devops_cli/security/sanitizer.py:def mask_secrets`, the mask that the record names for the run output.
- `list_files` on `src/devops_cli/sandbox` lists `src/devops_cli/sandbox/host.py`, the `HostSandbox` that wraps bubblewrap, and `list_files` on `k8s/devops/roadmap-service` lists `k8s/devops/roadmap-service/networkpolicy-egress.yaml` and `k8s/devops/roadmap-service/serviceaccount.yaml`, the controls that the record requires.
- The plan calls no function whose arguments need a checkout, a client or a network: each group writes one document, and the checks run in the checkout and open no connection.
- The first checks of the implementation against the real system are `uv run devops ci docs`, which verifies the generated references against the CLI and the configuration, and `uv run devops openspec check`, which validates the change folder against the base specs.
- The scope of #3288 moved the approval to the merge of the record's pull request and put the follow-up issues after that merge, so the plan maps both to a person and the record states the merge in its Status section.

## Existing Tool Considered

bubblewrap is the open, maintained sandbox that `HostSandbox` wraps (`src/devops_cli/sandbox/host.py`), and the agent-sandbox controller of kubernetes-sigs is the open candidate that the owner named on 2026-11-01; the record compares both with nsjail and gVisor, and this change adopts none of them and writes no code.

## Dependencies

None.
