# Tasks

## 1. Remove the token file in the config and prove a child cannot open it

Kind: behavior. Reads: `k8s/devops/renovate/configmap.yaml`, `k8s/devops/renovate/cronjob.yaml`, `tests/invariants/test_k8s_renovate.py`, `tests/commands/k8s/test_k8s.py`. Changes: `src/devops_cli/k8s/renovate_token.py` (new), `tests/invariants/test_k8s_renovate.py`, `k8s/devops/renovate/configmap.yaml`, `k8s/devops/renovate/cronjob.yaml`.
Adds: `RENOVATE_TOKEN_PATH`, `token_file_problems`

- [x] 1.1 Write the case `test_the_config_removes_the_token_before_a_child_process_can_read_it` in `tests/invariants/test_k8s_renovate.py` first. It takes the `config.js` and `config.json` keys of ConfigMap `renovate-config` from `k8s/devops/renovate/configmap.yaml`, writes both into a temporary folder, sets `DEVOPS_CLI_TOKEN_FILE` to a temporary token file, runs the script with `node`, and asserts that the exported config holds the token text and that a second `node` process that opens that path exits non-zero with `ENOENT`. It fails against the staged script, which leaves the file in place
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_renovate.py` fails on the base
- [x] 1.2 Add `src/devops_cli/k8s/renovate_token.py` with `RENOVATE_TOKEN_PATH = "/token/github-token"` and `token_file_problems(config_js: str) -> list[str]`, which reports a problem when the script does not hold that default path, does not read it, does not remove it, or removes it before the read. In `k8s/devops/renovate/configmap.yaml`, make `config.js` read `process.env.DEVOPS_CLI_TOKEN_FILE ?? '/token/github-token'` into a local, remove the same path with `unlinkSync` after the read, and export the value under the quoted key `'token'`, so Trivy KSV-0109 still reads no secret; correct the comments at lines 15 to 17 and 31 to 34 that say a task waits for #6020. In `k8s/devops/renovate/cronjob.yaml`, drop `readOnly: true` from the `token` mount of container `renovate` and correct the header comment that says no post-upgrade task runs until #6020. A failed read or removal stops Renovate at its start, so the pod fails closed
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_renovate.py` passes

## 2. Fail the k8s row when the config keeps the token

Kind: other. Reads: `tests/gate/k8s_checks/devops_runtime.py`, `tests/gate/k8s_render.py`, `src/devops_cli/k8s/renovate_token.py`, `k8s/devops/renovate/cronjob.yaml`. Changes: `tests/gate/k8s_checks/renovate.py` (new).

- [x] 2.1 Add `tests/gate/k8s_checks/renovate.py` in the shape of `tests/gate/k8s_checks/devops_runtime.py`, whose `check_*` functions the `k8s` row imports with no registration. `check_the_renovate_config_removes_the_token_file` takes the documents of the overlay `k8s/overlays/homelab/devops` with `applied_documents` of `tests/gate/k8s_render.py`, reads the `config.js` key of ConfigMap `renovate-config`, and asserts that `token_file_problems` returns no problem and that the exported key is the quoted `'token'`. `check_the_renovate_container_mounts_the_token_volume_writable` asserts that container `renovate` of CronJob `renovate` mounts the volume `token` with no `readOnly: true`
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 3. Correct ADR 0027 and name the token in memory

Kind: other. Reads: `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`, `tests/invariants/test_adr_records.py`. Changes: `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`.

- [x] 3.1 In `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`, replace the good consequence at line 57 with one that says a repository command reaches no key of the Service and no internal service, because `config.js` removes the installation token file before Renovate processes a repository. Add one bad consequence that names the installation token in the memory of the Renovate process, with its one hour of life, and the dropped capabilities and the node's `kernel.yama.ptrace_scope` of 1 that hold it. Name the `k8s` row and the new case of `tests/invariants/test_k8s_renovate.py` in the Confirmation section. Change no key of the front matter: the record is `proposed` and holds no `body-hash`
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py` passes
- [x] 3.2 Edit `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`
  - Verification: `$ uv run devops ci docs` passes

## 4. Hold the ADR body to the residual risk

Kind: other. Reads: `tests/invariants/test_k8s_renovate.py`, `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`. Changes: `tests/invariants/test_k8s_renovate.py`.

- [x] 4.1 Add `test_the_adr_names_the_token_in_memory_as_the_residual_risk` to `tests/invariants/test_k8s_renovate.py`, in the shape of `_license_lines`: read the path in `ADR` and assert that one line holds both `memory` and `one hour`, and that no line holds `a repository command that goes wrong reaches no key`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_renovate.py` passes

## 5. Document the removal, the writable mount and the node setting

Kind: other. Reads: `docs/CLUSTER.md`. Changes: `docs/CLUSTER.md`.

- [x] 5.1 Edit the Renovate section of `docs/CLUSTER.md`: container `renovate` mounts the volume `token` writable and `config.js` removes the file before Renovate processes a repository, so a task opens no token path; the `k8s` row fails a config that keeps the file or a read-only mount; and a person confirms the node setting with `kubectl debug node/<worker-node> -- chroot /host sysctl kernel.yama.ptrace_scope`, which prints 1. Replace the sentence at line 263 that says #6020 keeps the token away and then turns the tasks on
  - Verification: `$ uv run devops ci docs` passes
- [x] 5.2 Edit `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
