# Proposal

## Why

The cluster has about 21 Ingress objects and more service UIs with no Ingress, and no page lists the service UIs, so a person must remember each host name. Issue #4598 asks for Homepage as the cluster start page at the `start` host. The environment tree that would hold it has moved to dan-petty/homelab, so this repository records the choice in a decision record.

## What Changes

- Adds `docs/adr/0039-homepage-is-the-cluster-start-page.md`, an accepted record that chooses Homepage as the cluster start page at the `start` host, names the tools compared and refuses the other options.
- Regenerates the index table of `docs/adr/README.md` with `uv run devops docs generate`.
- Plans no manifest, because the environment-freeze row refuses a branch that changes an environment path outside the two product folders, so the start page objects land in dan-petty/homelab.
- Keeps the theme input of the design spec in the record: `color: stone` and no `theme` key, so the theme switcher stays.
- Has no spec delta, because the change writes two documents and no code, so no consumer observes another behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/adr/0039-homepage-is-the-cluster-start-page.md`, `docs/adr/README.md`

## Feasibility

- The probe says "The path `k8s/namespaces.yaml` is a file of the staging commit." and "The path `gethomepage.dev` is no file of the staging commit. No commit in the history deleted or renamed it.", so no cited path was removed and the start page directory would be new work.
- The issue cannot be built as written in this repository. `read_file tests/gate/k8s_checks/environment_freeze.py` showed `tests/gate/k8s_checks/environment_freeze.py:41:file.is_relative_to(_ENVIRONMENT_ROOT)`, `tests/gate/k8s_checks/environment_freeze.py:42:and not any(file.is_relative_to(folder) for folder in _PRODUCT_FOLDERS)` and `tests/gate/k8s_checks/environment_freeze.py:67:is an environment path, and dan-petty/homelab holds the environment.`, so every path that the issue names under `k8s` is an environment path.
- `read_file tests/gate/k8s_checks/environment_freeze.py` line 44 showed `tests/gate/k8s_checks/environment_freeze.py:44:and file.suffix != _DOCUMENT_SUFFIX`, so a Markdown file under `k8s` passes the row, and line 74 showed `tests/gate/k8s_checks/environment_freeze.py:74:these files and this check.`, so the README of the environment tree goes away with the environment files and the plan writes no section in it.
- `read_file tests/gate/k8s.py` showed `tests/gate/k8s.py:7:refuses a branch that changes an environment path, until step`, so the row that an earlier plan gave as a verify fails on a branch that holds the start page objects. This plan changes no path under `k8s`.
- `read_file docs/HOMELAB_REPO_SWITCH.md` lines 180-300 showed `docs/HOMELAB_REPO_SWITCH.md:184:The rule is by folder, so a new environment file is refused too.`, so a new file of the start page is refused as well, and `docs/HOMELAB_REPO_SWITCH.md:268:Homelab CI runs the environment checks that #5131 lists.` gives the environment checks to the CI of dan-petty/homelab.
- `docs/HOMELAB_REPO_SWITCH.md:254:delete the override path of #1290: the constants` removes `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK` and the override path at step 15, so the plan adds no entry to a table that is on its way out.
- The record is the part that this repository keeps: `docs/adr/README.md:11:- A dependency or a tool.` names a tool as a reason to write a record, and `docs/adr/README.md:40:3. The merge by the owner accepts the record.` gives the approval that a merge carries.
- `list_files docs/adr` listed `docs/adr/0038-owner-decisions-on-what-agents-may-do.md` as the newest record on `origin/main`, so the new record is `docs/adr/0039-homepage-is-the-cluster-start-page.md`.
- `read_file src/devops_cli/roadmap/adr.py` line 5 showed `src/devops_cli/roadmap/adr.py:5:`consulted` and `informed`) and the keys of this project (`issue`, `tracker`, `supersedes`,`, so the front matter takes `issue` and `body-hash` as well as the keys of MADR 4.
- `read_file src/devops_cli/docs/adr_records.py` lines 30-47 showed `src/devops_cli/docs/adr_records.py:32:_MAX_BODY_WORDS: Final = 1000`, `src/devops_cli/docs/adr_records.py:33:_MAX_TITLE_WORDS: Final = 10` and `src/devops_cli/docs/adr_records.py:34:_MAX_SLUG_CHARACTERS: Final = 60`, so the title `Homepage is the cluster start page` has 6 words and the slug `homepage-is-the-cluster-start-page` has 34 characters.
- `read_file tests/invariants/test_adr_records.py` showed `tests/invariants/test_adr_records.py:18:def test_each_record_keeps_the_rules_of_the_decision_records() -> None:` and `tests/invariants/test_adr_records.py:22:def test_the_index_of_the_readme_is_the_generated_index() -> None:`, so one verify checks the record and its index row.
- `docs/adr/README.md:142:writes this table from the front matter of each record` names the generator, so the step regenerates the index and edits no row by hand.
- `list_files tests/commands/k8s` listed no `test_k8s_network_policies.py`, so the fourth criterion names a path that no commit holds; the checks of the manifests of the tree are the modules of `tests/gate/k8s_checks/`.
- `uv run devops ci test tests/invariants/test_adr_records.py` needs a checkout of the repository, no client of a service and no network; `uv run devops docs generate`, which the step runs to write the index, needs the same checkout and no client and no network.
- The verify introduces no program: `uv run devops ci test tests/invariants/test_adr_records.py` runs `pytest` and `markdown-it-py` from the runner image, neither is `NOT_IN_RUNNER`, and the pod settings `runAsNonRoot: true`, `capabilities.drop: ALL`, `readOnlyRootFilesystem: true` and `seccompProfile: RuntimeDefault` apply.
- The security finding is answered at its place: `security` is non-blank and states what crosses a trust boundary, what a person must confirm and which test fails, and the change creates no cluster object, role or policy.
- The `k8s/startpage` finding is answered: the task of the group names only paths that the commit holds or that the group creates, and the record names the start page directory of the environment tree in prose, with no path in a code span.
- The what_changes finding is answered: each path that `what_changes` names is `docs/adr/README.md`, which the group changes, or the record, which the group creates, and no item names the freeze check.

## Existing Tool Considered

gethomepage/homepage (GPL-3.0, maintained, last activity 2026-11-12) covers the need: it builds the link list from Kubernetes Ingress and Traefik IngressRoute annotations, takes its groups from YAML, and ships an image that a digest pins. The change builds no code of its own.

## Dependencies

- Pull request #6966 changes `src/devops_cli/config/constants.py`, a file that this plan leaves unchanged, so the two merge in either order.
- Pull request #6978 changes `k8s/README.md`, a file that this plan leaves unchanged, so the two merge in either order.
- #4738: it delivered the design token build whose `color: stone` input the record names.
- #4542: it delivered the deploy-stack patch of a container environment value that the record names as the way the configured domain reaches the page.
