# Tasks

## 1. Add the start page opt-in rule for a routing object

Kind: behavior. Reads: `k8s/ingress/ingress-routes.yaml`, `k8s/mattermost/mattermost.yaml`, `k8s/devops/roadmap-service/ingress.yaml`, `tests/k8s/test_kubernetes_contract.py`, `tests/commands/k8s/test_k8s.py`. Changes: `src/devops_cli/k8s/start_page.py` (new), `tests/k8s/test_start_page.py` (new).
Adds: `START_PAGE_GROUPS`, `START_PAGE_ANNOTATIONS`, `START_PAGE_MACHINE_ENDPOINTS`, `START_PAGE_DOMAIN_PLACEHOLDER`, `start_page_routed_hosts`, `start_page_problems`

- [ ] 1.1 `tests/k8s/test_start_page.py::test_start_page_problems_fails_a_machine_endpoint_that_opts_in` fails at import, because `devops_cli.k8s.start_page` does not exist yet, and the cases of `start_page_problems` follow it
  - Verification: `$ uv run devops ci test tests/k8s/test_start_page.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/k8s/start_page.py` with `START_PAGE_GROUPS` (`AI`, `Observability`, `Platform`, `Source Control`, `Collaboration`), `START_PAGE_ANNOTATIONS` (`enabled`, `group`, `name`, `description`, `href`, `pod-selector`, `weight`, with optional `icon` allowed non-blank), `START_PAGE_MACHINE_ENDPOINTS` (`devops/roadmap-service` for the product base), `START_PAGE_DOMAIN_PLACEHOLDER` (`{{HOMEPAGE_VAR_DOMAIN}}`), `start_page_routed_hosts` and `start_page_problems`. `start_page_routed_hosts` reads the hosts of an Ingress from its rules, of an IngressRoute from the `Host(...)` of each match, and of a Mattermost resource from `spec.ingress.host` as in `k8s/mattermost/mattermost.yaml`. `start_page_problems` keeps the first document of each kind, namespace and name, reads annotations from `metadata.annotations` or `spec.ingress.annotations` of a Mattermost resource, fails a machine endpoint that carries any `gethomepage.dev` annotation, and for every other routing object fails a missing required annotation, blank `name`/`description`/`pod-selector`/`icon`, an `enabled` that is not `true`, a group outside the five, an `href` that is not `https://`, lacks `{{HOMEPAGE_VAR_DOMAIN}}` in its host, or targets a host the object does not route once that placeholder reads as `example.com`, and a `weight` that is not an integer. Write the unit cases in `tests/k8s/test_start_page.py` first
  - Verification: `$ uv run devops ci test tests/k8s/test_start_page.py` passes

## 2. Run the start page rule on the product base

Kind: other. Reads: `tests/gate/k8s_checks/roadmap_service.py`, `tests/gate/k8s_checks/valkey_memory.py`, `tests/gate/k8s_render.py`, `tests/gate/runner.py`, `src/devops_cli/k8s/start_page.py`, `k8s/overlays/homelab/devops/kustomization.yaml`. Changes: `tests/gate/k8s_checks/start_page.py` (new).

- [ ] 2.1 Add `tests/gate/k8s_checks/start_page.py` following `tests/gate/k8s_checks/roadmap_service.py` and `tests/gate/k8s_checks/valkey_memory.py`: add `check_each_routing_object_of_the_product_base_opts_in_or_is_a_machine_endpoint` taking `applied_documents` of `k8s/overlays/homelab/devops` and `k8s/devops/roadmap-service/ingress.yaml`, joining them, and asserting `start_page_problems` returns no finding (showing any findings in the failure message), plus negative-control `check_*` functions asserting `start_page_problems` fails an Ingress with neither opt-in nor machine-endpoint status and fails `devops/roadmap-service` if it carries `gethomepage.dev/enabled`. State in the module docstring that the environment objects and their annotations live in dan-petty/homelab (#4600) and that both applies share the webhook Ingress counted once
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 3. State the start page contract in the cluster README

Kind: other. Reads: `k8s/README.md`, `k8s/catalog.toml`, `src/devops_cli/k8s/start_page.py`. Changes: `k8s/README.md`.

- [ ] 3.1 Extend the paragraph at `k8s/README.md` line 649, beside the description rule of `k8s/catalog.toml`, with the start page contract: the seven required annotations and optional icon, the five groups, the `https://<name>.{{HOMEPAGE_VAR_DOMAIN}}/<path>` link rule on a routed host, the machine-endpoint rule (noting `devops/roadmap-service` in `src/devops_cli/k8s/start_page.py` for the product base, that machine endpoints carry no `gethomepage.dev` annotation, and that the 11 service UI objects and the environment API and exporter routes live in dan-petty/homelab while the `k8s` row checks the product base). Name no real host
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: The 11 objects carry the annotations, and each tile shows after the sync with a running pod., The 11 objects are environment paths of dan-petty/homelab since step 11, so a homelab pull request adds the annotations, and only a person reads the tiles after a sync with a running pod; the live check is #7101.
- Group 2: The invariant test fails for an Ingress that neither opts in nor is on the machine endpoint list, and for `devops/roadmap-service` if it opts in.
- Group 3: No real host is in the repository.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
