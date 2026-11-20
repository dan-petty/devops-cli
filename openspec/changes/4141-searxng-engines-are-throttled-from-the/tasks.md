# Tasks

## 1. Fail the live check on a Stack Exchange engine that must stay off

Kind: behavior. Reads: `src/devops_cli/k8s/searxng_check.py`, `tests/k8s/test_searxng_check.py`, `k8s/devops/searxng/configmap.yaml`, `tests/commands/k8s/test_k8s.py`, `tests/commands/k8s/test_k8s_searxng_check.py`. Changes: `src/devops_cli/k8s/searxng_check.py`, `tests/k8s/test_searxng_check.py`.

- [ ] 1.1 `tests/k8s/test_searxng_check.py::test_the_engines_that_stay_off_are_the_keyed_and_suspended_ones` fails today with the seven-name tuple, and the new `tests/k8s/test_searxng_check.py::test_a_stack_exchange_engine_that_must_stay_off_fails_the_check` covers the scenario `A Stack Exchange engine that must stay off fails the check`
  - Verification: `$ uv run devops ci test tests/k8s/test_searxng_check.py` fails on the base
- [ ] 1.2 Add `stackoverflow`, `askubuntu` and `superuser` to `OFF_ENGINES` in `src/devops_cli/k8s/searxng_check.py`, and state in the comment above it that the three answer HTTP 400 from `api.stackexchange.com` with no key and that a reply which names one fails the check. Change the module docstring line that names the engines which stay off. Update `tests/k8s/test_searxng_check.py`: the tuple assertion takes the ten names, the module docstring counts ten, and the new case asserts that a reply whose unresponsive engines hold `stackoverflow` gets one problem that names it
  - Verification: `$ uv run devops ci test tests/k8s/test_searxng_check.py` passes

## 2. Remove the three Stack Exchange engines from the settings

Kind: other. Reads: `k8s/devops/searxng/configmap.yaml`, `src/devops_cli/k8s/searxng_check.py`, `tests/commands/k8s/test_k8s_devops_stack.py`. Changes: `k8s/devops/searxng/configmap.yaml`, `tests/commands/k8s/test_k8s_devops_stack.py`.

- [ ] 2.1 Delete the three Stack Exchange entries from the list under `keep_only` in `k8s/devops/searxng/configmap.yaml`, so the list holds `duckduckgo`, `wikipedia`, `github`, `arxiv`, `mdn` and `docker hub`. Extend the header comment: the 3-hour log of 2026-11-08 records HTTP 400 from `api.stackexchange.com` for the three with no key in the request and a 180 s suspension for too many requests; the log holds no reply body, so the cause of the 400 is not proven; the three need a Stack Exchange API key, which is a Secret a person creates; and `devops k8s searxng-check` fails a reply that names one. Add no key, no retry and no suspension value
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 3. Record the six kept engines and the log facts in the cluster documentation

Kind: other. Reads: `docs/CLUSTER.md`, `k8s/devops/searxng/configmap.yaml`. Changes: `docs/CLUSTER.md`.

- [ ] 3.1 Rewrite the bullet `- **The engines.**` of `docs/CLUSTER.md`: name the six kept engines, drop `stackoverflow`, `askubuntu` and `superuser` from the kept list and from the `it` list, record that the three answered HTTP 400 from `api.stackexchange.com` with no key and no hit in the 3-hour log of 2026-11-08 and were suspended for too many requests, that the cause of the 400 is not proven, and that `devops k8s searxng-check` fails a reply that names one. Keep the sentences on the provider categories, the upstream-suspended engines and the absent retry loop
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Edit `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: The issue holds the measure: the query rate for each backend and the `result` share, over at least 3 days., Only a person writes the measure into the issue, and it needs at least 3 days of `devops_cli_web_searches_total` by `backend` and `result` from the live Service, split into Service traffic and check or manual traffic; the refine comment records that item under #4201.
- Group 1: A command or test that fails today, for example a test over the `searxng-settings` ConfigMap that checks the chosen engine set (no engine in `keep_only` that the measure shows as blocked by the cluster egress address), and a `devops k8s searxng-check` run that gets hits for the `general` category.
- Pending person: The cause is named: query rate or the cluster egress address., Telling the two causes apart needs the 3-day measure and a query from another egress address, which no tool of this run sends and no runner can send; the refine comment records that item under #4201.
- Group 1: No retry loop is added (#4094).
- Group 2: Metasearch over many key-free engines from one endpoint
- Group 2: Engine allow-list through `keep_only` in the settings
- Pending person: Per-engine suspension and engine API-key settings, The plan sets no per-engine suspension and no engine API key: a key is a Secret that a person creates, and the suspension value waits on the 3-day measure under #4201.
- Group 2: No key and no user store for the search path
- Pending person: No per-backend query-rate or result-share metric, The metric `devops_cli_web_searches_total` already holds the labels `backend` and `result`; the 3-day measure needs the live Service, and the refine comment records it under #4201.
- Pending person: CAPTCHA can repeat when an engine sets no suspension, The pinned image sets no suspension for the `duckduckgo` CAPTCHA; the measure under #4201 checks that against the image and decides the suspension value.
- Pending person: No way to tell query rate from an egress-address flag, Telling the rate from the address flag needs the 3-day measure and a query from another egress address, which no runner can send; the refine comment records that item under #4201.
- Pending person: Stack Exchange engines need a Secret that a person creates, Only a person creates the Stack Exchange API key Secret; the plan adds no key, and the item under #4201 holds the keyed engines.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
