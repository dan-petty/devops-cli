# Proposal

## Why

The start page lists a service only when the object that routes its host carries the `gethomepage.dev` annotations, so a service UI can stay hidden and a machine endpoint can show by mistake (#4600). This plan puts that rule in code, with tests over an Ingress, an IngressRoute and a Mattermost resource, and makes the `k8s` row of `devops ci` enforce it on the routing objects that this repository deploys, so a start-page tile never opens the webhook route of the roadmap Service.

## What Changes

- Add `src/devops_cli/k8s/start_page.py` with the start page rule: the seven `gethomepage.dev` annotations, optional `icon`, the five groups, the machine-endpoint list, `{{HOMEPAGE_VAR_DOMAIN}}` validation against routed hosts, and one count for each kind, namespace and name.
- Add `tests/k8s/test_start_page.py` with unit cases of `start_page_problems` covering an Ingress, an IngressRoute and a Mattermost resource, a missing opt-in, an incomplete opt-in, a machine endpoint that opts in, an unknown group, a missing placeholder or unrouted link host, and a duplicate document.
- Add `tests/gate/k8s_checks/start_page.py`, so the `k8s` row of `devops ci` validates the product base and runs negative-control checks that fail an Ingress with neither opt-in nor machine-endpoint status, and fail the roadmap Service webhook Ingress if it opts in.
- State the opt-in contract in `k8s/README.md`, next to the description rule that already cites #4600.
- Carry a spec delta of two added requirements under `ci-gate-rows`, because a new rule of the `k8s` row changes what a pull request author observes.
- Leave the 11 service UI annotations, the environment API and exporter machine-endpoint entries, and the checks over environment objects to dan-petty/homelab, because the `k8s` row refuses a branch that changes an environment path.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-gate-rows`: The k8s row refuses a start-page opt-in on a machine endpoint, The k8s row accepts only a known group and a routed link host

## Impact

- Code: `src/devops_cli/k8s/start_page.py`
- Documents: `k8s/README.md`
- Tests: `tests/k8s/test_start_page.py`, `tests/gate/k8s_checks/start_page.py`

## Feasibility

- `tests/invariants/test_k8s_manifests.py:5:and no test asserts a value of them (#6060).` reserves manifest-value assertions for the `k8s` row and kube-linter, so the start page rule runs in `tests/gate/k8s_checks/` rather than under `tests/invariants/`.
- `k8s/README.md:649:A service with a Homepage UI takes its description from the` and `k8s/catalog.toml:11:(#4600), which is its one description.` are the only `gethomepage` matches outside `openspec/changes/archive/`, so no manifest under `k8s/` carries a `gethomepage.dev` annotation yet.
- `k8s/ingress/ingress-routes.yaml:488:kind: IngressRoute` and `k8s/mattermost/mattermost.yaml:23:ingress:` sit in the frozen environment tree, while `k8s/devops/roadmap-service/ingress.yaml:2:kind: Ingress` is the only routing object of the product base.
- None of `src/devops_cli/k8s/start_page.py`, `tests/k8s/test_start_page.py` or `tests/gate/k8s_checks/start_page.py` exist in the repository yet, so all three files are new. `src/devops_cli/k8s/argocd_overrides.py:147:def _host_fields(doc: dict[str, Any]) -> list[tuple[str, str]]:` is not reused because it emits JSON-pointer strings across `ConfigMap`, `Deployment`, `tls` and raw Traefik `match` filters rather than parsed hostnames, and step 15 removes it (`docs/HOMELAB_REPO_SWITCH.md:254:delete the override path of #1290:`).
- The 11 service UI manifests cannot change in this repository: `tests/gate/k8s_checks/environment_freeze.py:26:_PRODUCT_FOLDERS: Final[tuple[PurePosixPath, ...]] = (`, `tests/gate/k8s_checks/environment_freeze.py:44:and file.suffix != _DOCUMENT_SUFFIX`, `tests/gate/k8s_checks/environment_freeze.py:67:is an environment path, and dan-petty/homelab holds the environment.`, and `tests/gate/k8s.py:7:refuses a branch that changes an environment path, until` block environment manifest edits while allowing Markdown edits to `k8s/README.md`.
- `k8s/overlays/homelab/devops/kustomization.yaml:5:- ../../../devops` and `k8s/devops/kustomization.yaml:21:- roadmap-service` show that the homelab overlay renders the product base and includes the roadmap Service Ingress.
- `k8s/devops/roadmap-service/ingress.yaml:15:- host: hooks.example.com` and `k8s/devops/roadmap-service/ingress.yaml:18:- path: /webhooks/github` show that the one routing object of the product base is a webhook machine endpoint, so the machine-endpoint list of this repository holds `(devops, roadmap-service)` alone.
- `k8s/mattermost/mattermost.yaml:23:ingress:`, `k8s/mattermost/mattermost.yaml:25:host: mattermost.example.com` and the nested `annotations:` mapping show that a Mattermost resource stores its route annotations under `spec.ingress`.
- `tests/gate/runner.py:45:if name.startswith("check_") and function.__module__ == module.__name__` and `tests/gate/k8s.py:14:import tests.gate.k8s_checks as k8s_checks` show that adding `tests/gate/k8s_checks/start_page.py` joins the `k8s` row with no registry change, and `tests/gate/k8s_checks/valkey_memory.py` shows the precedent for placing negative-control `check_*` functions in a `k8s_checks` module.
- `openspec/specs/ci-gate-rows/spec.md` defines 28 requirements (including `The k8s row refuses a change to an environment path` and `The k8s row renders each application once`); neither added requirement name exists yet, and both added requirements stay within the 500-character limit.
- `tests/gate/k8s_render.py:83:def applied_documents(path: Path) -> list[dict[str, Any]]:` needs only a checkout of the repository (`kubectl kustomize` and YAML parsing), and `check_docs` (`uv run devops ci docs`) compares checked-out docs against generated output offline with no network or cluster client.
- The checks invoke `uv`, `devops`, `pytest`, `kubectl` and `git`, all present in the runner image; failure classes are `test` for the `k8s` row and `lint` for the `docs` row, under `runAsNonRoot: true`, `capabilities.drop: ALL`, `readOnlyRootFilesystem: true` and `seccompProfile: RuntimeDefault`, with no writes outside temporary storage.
- Against the real system, `uv run devops ci --check --only k8s` exits 0 on the clean branch (running both the product-base check and negative controls) and exits 1 if `k8s/devops/roadmap-service/ingress.yaml` gains `gethomepage.dev/enabled` in the working tree; `uv run devops ci docs` verifies documentation parity.
- #4598 delivered `docs/adr/0039-homepage-is-the-cluster-start-page.md` (archived at `openspec/changes/archive/2026-11-25-4598-deploy-homepage-as-the-cluster-start/`), and `docs/adr/0039-homepage-is-the-cluster-start-page.md:33:live in dan-petty/homelab, because environment manifests moved out of this repository.` places the start page directory and `startpage` Application in dan-petty/homelab rather than on this repository's default branch.

## Existing Tool Considered

gethomepage/homepage (GPL-3.0, maintained) is already in use: it reads the `gethomepage.dev` annotations of the routing object and renders the tile and its group. No open tool enforces the opt-in rule, because the rule checks the seven annotations, requires `{{HOMEPAGE_VAR_DOMAIN}}` against routed hosts of the render, and keeps a machine-endpoint list. The change builds about 170 lines of rule code and about 10 test and gate cases: about 40k tokens and 2 hours to build, about 2k tokens a month to keep, and about 8k tokens to fix. The change deletes no internal code.

## Dependencies

- #4598: delivered `docs/adr/0039-homepage-is-the-cluster-start-page.md` (archived at `openspec/changes/archive/2026-11-25-4598-deploy-homepage-as-the-cluster-start/`), recording Homepage as the cluster start page and placing its deployment manifests and `startpage` Application in dan-petty/homelab; the live rendered-tile check is tracked separately in #7101.
