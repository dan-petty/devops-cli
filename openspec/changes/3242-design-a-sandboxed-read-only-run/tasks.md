# Tasks

## 1. Write the decision record and its decision

Reads: `SECURITY.md`, `CONTEXT.md`, `k8s/devops/roadmap-service/deployment.yaml`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/runner_tools.py`, `docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md`. Changes: `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` (new).

- [x] 1.1 Create the record with the title, the problem (8 of 48 findings in the first five plan fixes rest on a premise that only a run shows, and a read command deleted a key), a `## Status` section that states that the merge of this pull request is the approval and names the merge commit through `git log --follow`, and a `## Decision` section with five parts. The allow-list: `devops <command> --help` for every command, plus each command that the MCP exposure table marks read-only and that publishes no path option, and no other command, including a command that an issue quotes. The seven isolation controls: a temporary HOME on an emptyDir, a copy of the config with no credential, a read-only copy of the staged commit, no network by the egress NetworkPolicy, a CPU, memory and wall-clock cap, UID 1000, and no service account token, applied by a container with the `RuntimeDefault` seccomp profile. The run location: a separate Kubernetes Job that the planner creates for one run, which refuses the Service pod that calls `plan_stage` and refuses the planner process. The output: a byte cap, a line cap, `mask_secrets`, and a quote under `## Feasibility` with the command and the exit code. The input of #2695: the owner decision of 2026-10-30 separates privilege by container and rejects bubblewrap and `unshare`, #2695 owns the agent-sandbox question, and this record does not change #2695
  - Verification: `uv run devops ci docs` passes
- [x] 1.2 Add `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` with the status, the decision, the allow-list, the isolation controls, the run location and the output rules
  - Verification: `uv run devops ci docs` passes

## 2. Add the alternatives, the rejected options, the proof tests and the follow-ups

Reads: `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md`, `src/devops_cli/sandbox/host.py`, `k8s/devops/roadmap-service/networkpolicy-egress.yaml`, `tests/sandbox/test_host_sandbox.py`. Changes: `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md`.

- [ ] 2.1 Add to the record a `## Considered Options` section that compares bubblewrap, nsjail, gVisor and the agent-sandbox controller of kubernetes-sigs, states what each one lacks, and states the cost of the container boundary (about 3,000 tokens to write, about 500 tokens a month to keep, one day) and of a sandbox built from scratch (about 40,000 tokens, two weeks). Add a `## Rejected options` section that names the deny list, a command that an issue quotes, `--help` only, `HostSandbox` with bubblewrap, a NetworkPolicy alone, the Service pod, a stage Job, the full output, a model summary of the output and a fake executor. Add a `## Proof` section that names three tests in one new test module of the roadmap tests folder: a write outside the read-only copy of the staged commit, a read of a credential and of the service account token, and an outbound connection. They run offline on the rendered Job manifest, and one live test marked `k8s` runs the same three cases. Add a `## Follow-ups` section that lists the run Job manifest, the allow-list builder, the output cut and mask, and the proof tests, and that states that each filed issue names this record and lists #3242. Add a `## Consequences` section
  - Verification: `uv run devops ci docs` passes
- [ ] 2.2 Extend `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md` with the comparison, the rejected options, the proof tests, the follow-ups and the consequences
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 2: An ADR in `docs/adr/` states the decision, the alternatives and the rejected options.
- Pending person: A person has approved it in a comment on this issue., The scope of #3288 moved the approval to the merge of the ADR pull request, and only a person merges a pull request.
- Pending person: The follow-up implementation issues exist and name this ADR., Filing an issue is a GitHub action, and no group of this pull request files one; the Service files each follow-up after the merge, and each lists #3242 as a dependency.
