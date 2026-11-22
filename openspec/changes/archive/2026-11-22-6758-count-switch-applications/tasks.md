# Tasks

## 1. Count the Applications of the switch from the copy

Reads: `docs/HOMELAB_REPO_SWITCH.md`, `k8s/devops-cli-copy.json` of dan-petty/homelab (keys only).

Changes: `docs/HOMELAB_REPO_SWITCH.md`.

- [x] 1.1 Define "the Applications of the copy" and "the child Applications of `cluster`" in the rules, and write the finalizer rule with no count
  - Verification: `$ grep -c 'Application of the copy' docs/HOMELAB_REPO_SWITCH.md`
- [x] 1.2 Write each count of steps 11, 13, 14, 17 and of the revert as "each Application of the copy" or "each child Application of `cluster`"
  - Verification: `$ grep -n -E '\b3[1-6]\b' docs/HOMELAB_REPO_SWITCH.md`
- [x] 1.3 Keep the dated baseline of 2026-11-13 in step 10, and add the dated baseline of 2026-11-22
  - Verification: `$ uv run devops ci --check --only docs,domain`

## Criteria

- Group 1: `grep -n -E '\b3[1-6]\b' docs/HOMELAB_REPO_SWITCH.md` SHALL find only the lines of the dated baselines of step 10.
- Group 1: `uv run devops ci --check --only docs` SHALL pass.
- Group 1: The document SHALL hold no real domain, host, private address or Application YAML.
