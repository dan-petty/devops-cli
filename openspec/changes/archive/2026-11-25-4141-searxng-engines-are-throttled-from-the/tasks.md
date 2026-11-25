# Tasks

## 1. Fail the live check on a Stack Exchange engine that must stay off

Kind: behavior. Reads: `src/devops_cli/k8s/searxng_check.py`, `tests/k8s/test_searxng_check.py`, `tests/commands/k8s/test_k8s_searxng_check.py`, `tests/commands/k8s/test_k8s.py`. Changes: `src/devops_cli/k8s/searxng_check.py`, `tests/k8s/test_searxng_check.py`.

- [x] 1.1 `test_the_engines_that_stay_off_are_the_keyed_and_suspended_ones` fails on the base on the seven-name tuple at `tests/k8s/test_searxng_check.py:55:assert sorted(OFF_ENGINES) == sorted(`; `test_a_hit_of_an_engine_that_stays_off_is_a_problem_that_names_the_engine` gains the cases stackoverflow, askubuntu and superuser; and `test_an_engine_that_stays_off_and_is_listed_as_unresponsive_is_a_problem` gains a stackoverflow case over the `unresponsive_engines` list of a reply. The cases cover the scenario `A Stack Exchange engine is listed as unresponsive` of the requirement `Engines that stay off`
  - Verification: `$ uv run devops ci test tests/k8s/test_searxng_check.py` fails on the base
- [x] 1.2 Add stackoverflow, askubuntu and superuser to the tuple `src/devops_cli/k8s/searxng_check.py:70:OFF_ENGINES: Final = ("brave", "braveapi", "google", "bing", "startpage", "mojeek", "qwant")` in `src/devops_cli/k8s/searxng_check.py`, and extend the comment above it, which starts at `src/devops_cli/k8s/searxng_check.py:67:# The scraping engines that the upstream sites suspended in October 2026 (SearXNG issues 6866 and`, with the HTTP 400 from api.stackexchange.com with no key in the request and the note that the cause of the 400 is not proven. Update `tests/k8s/test_searxng_check.py` as the failing cases name. Keep `_off_engines` and `reply_problems` as they are, because a prefix match covers the new names. Add no retry loop and no wait
  - Verification: `$ uv run devops ci test tests/k8s/test_searxng_check.py` passes

## 2. Remove the three Stack Exchange engines from the settings

Kind: other. Reads: `k8s/devops/searxng/configmap.yaml`, `src/devops_cli/k8s/searxng_check.py`, `docs/CLUSTER.md`. Changes: `k8s/devops/searxng/configmap.yaml`.

- [x] 2.1 Edit `k8s/devops/searxng/configmap.yaml`: delete the three Stack Exchange entries from the list under `keep_only` at line 33, so the list holds duckduckgo, wikipedia, github, arxiv, mdn and docker hub, the engines that answer the general, it and science categories. Extend the header comment of the same file, which starts at `k8s/devops/searxng/configmap.yaml:1:# The settings of SearXNG (#3924).`: the log of 2026-11-08 records HTTP 400 from api.stackexchange.com for the three with no key in the request and a suspension for too many requests, and the log holds no reply body, so the cause of the 400 is not proven. Then run `uv run devops ci --check --only k8s` (a person runs `uv run devops k8s searxng-check` on the cluster after rollout). Add no engine name, no key, no retry and no suspension value
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 3. Record the six kept engines and the log facts in the cluster document

Kind: other. Reads: `docs/CLUSTER.md`, `k8s/devops/searxng/configmap.yaml`, `src/devops_cli/k8s/searxng_check.py`. Changes: `docs/CLUSTER.md`.

- [x] 3.1 Rewrite the engines bullet of `docs/CLUSTER.md` (`docs/CLUSTER.md:260:keeps nine engines that need no key`): name the six kept engines duckduckgo, wikipedia, github, arxiv, mdn and docker hub, drop stackoverflow, askubuntu and superuser from the kept list and from the engines that answer it, so that list reads github, mdn and docker hub, and record that the three answered HTTP 400 from api.stackexchange.com with no key, were suspended for too many requests, and that the cause of the 400 is not proven. Say that the general category asks duckduckgo and wikipedia, and that the 1 hit of the general row on 2026-11-08 came while duckduckgo answered a CAPTCHA, so the log names no engine for it. Rewrite the off-engine list of the check bullet (`docs/CLUSTER.md:266:It fails a row when a reply lacks one of the seven keys`), so it names the ten engines of `OFF_ENGINES`. Keep the sentences on the provider categories, the suspension of a refusing engine and the absent retry loop
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: The issue holds the measure: the query rate for each backend and the `result` share, over at least 3 days., Only a person writes the measure into the issue, and it needs at least 3 days of devops_cli_web_searches_total by backend and result from the live Service, split into Service traffic and check or manual traffic. The refine comment records that work under #4201.
- Group 2: A command or test that fails today, for example a test over the `searxng-settings` ConfigMap that checks the chosen engine set (no engine in `keep_only` that the measure shows as blocked by the cluster egress address), and a `devops k8s searxng-check` run that gets hits for the `general` category.
- Pending person: The cause is named: query rate or the cluster egress address., Telling the two causes apart needs the 3-day measure and a query sent from another egress address, which no tool of this run sends and no runner can send. The refine comment records that work under #4201.
- Group 1: No retry loop is added (#4094).
- Group 2: Metasearch over many key-free engines from one endpoint
- Group 2: Engine allow-list through `keep_only` in the settings
- Pending person: Per-engine suspension and engine API-key settings, A suspension value needs the measure and a check against the pinned image, and the Stack Exchange engine key is a Secret that a person creates. The refine comment records that work under #4201, and this change removes the three engines that need the key instead.
- Group 2: No key and no user store for the search path
- Pending person: No per-backend query-rate or result-share metric, SearXNG holds no per-backend rate or result-share metric. The project already counts each attempt in devops_cli_web_searches_total by backend and result, and only a person writes the 3-day measure into the issue under #4201, so this change adds no metric.
- Pending person: CAPTCHA can repeat when an engine sets no suspension, The log of 2026-11-08 records suspended_time=0 for the duckduckgo CAPTCHA, and the issue says the effect of a suspension value must be checked against the pinned image after the measure. The refine comment records that work under #4201, so this change sets no suspension value.
- Pending person: No way to tell query rate from an egress-address flag, Telling a query rate from a flag on the egress address needs the 3-day measure and the same query sent from another egress address, which only a person can send. The refine comment records that work under #4201.
- Pending person: Stack Exchange engines need a Secret that a person creates, Only a person creates the Stack Exchange API key Secret. This change removes stackoverflow, askubuntu and superuser from keep_only, so the settings keep no engine that needs a key and no Secret is needed for the search path.

## Workflow follow-up

- Pending a person: after the rollout of `k8s/devops/searxng/configmap.yaml`, run `uv run devops k8s searxng-check` on the cluster and confirm that the `json-general` row holds at least one hit and that no reply names an engine that must stay off (a `json-general` failure on a DuckDuckGo CAPTCHA belongs to #4201).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
