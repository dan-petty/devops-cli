# Tasks

## 1. Keep no engine that never answers

Kind: behavior. Reads: `k8s/devops/searxng/configmap.yaml`, `tests/invariants/test_k8s_searxng.py`, `tests/fixtures/searxng/default_engine_names.txt`. Changes: `tests/invariants/test_k8s_searxng.py`, `tests/fixtures/searxng/engines_that_never_answer.txt` (new), `k8s/devops/searxng/configmap.yaml`.

- [x] 1.1 Write the failing tests first in `tests/invariants/test_k8s_searxng.py`. `test_the_settings_keep_no_engine_that_never_answers` asserts that no name of `keep_only` is a name in `tests/fixtures/searxng/engines_that_never_answer.txt`. `test_the_dead_engines_file_gives_a_date_and_a_reason_for_real_engines` asserts that the first name of the file is `pypi`, that each line has a date and a reason, and that each name is an engine of the default settings. Change `test_the_settings_keep_only_engines_that_need_no_key` to list nine engines, without `pypi`. Add the fixture file with the line for `pypi`. The first and the third test fail on the base because `keep_only` holds `pypi`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py` fails on the base with `pypi` in `keep_only`
- [x] 1.2 Remove `- pypi` from `keep_only` in `k8s/devops/searxng/configmap.yaml`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py -k "never_answers or need_no_key or dead_engines"` passes

## 2. Explain the two log lines in the ConfigMap

Kind: behavior. Reads: `k8s/devops/searxng/configmap.yaml`, `tests/invariants/test_k8s_searxng.py`. Changes: `tests/invariants/test_k8s_searxng.py`, `k8s/devops/searxng/configmap.yaml`.

- [x] 2.1 Write the failing test `test_the_configmap_says_why_the_two_log_lines_of_the_start_are_harmless` in `tests/invariants/test_k8s_searxng.py`. It reads the file `k8s/devops/searxng/configmap.yaml` and asserts that the text names `X-Forwarded-For`, `searx/botdetection/trusted_proxies.py`, `limiter.toml`, `searx/botdetection/config.py` and the word `harmless`
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py -k log_lines` fails on the base
- [x] 2.2 Add a comment above `apiVersion` in `k8s/devops/searxng/configmap.yaml` (outside the text of `settings.yml`, which the secret and e-mail test reads). It says that the ERROR "X-Forwarded-For nor X-Real-IP header is set!" comes from `log_error_only_once` in `searx/botdetection/trusted_proxies.py` and shows once, because the roadmap Service sends no proxy header and `server.limiter: false` means that no code uses the client address, and that the WARNING "missing config file: /etc/searxng/limiter.toml" comes from `Config.from_toml` in `searx/botdetection/config.py`, because `limiter.initialize` reads the config even with the limiter off and a missing file leaves the defaults. It says that both lines are harmless and that no `limiter.toml` is mounted. It also says that `request_timeout` stays at 5.0 on the evidence of the measure of 2026-11-07
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py -k "log_lines or limiter_and_serve_json or secret"` passes

## 3. Document the engine list

Kind: documents. Reads: `k8s/README.md` (the line "The engines."), `tests/invariants/test_k8s_searxng.py`. Changes: `k8s/README.md`, `tests/invariants/test_k8s_searxng.py`.

- [x] 3.1 Write `test_the_readme_lists_the_engines_that_the_settings_keep` in `tests/invariants/test_k8s_searxng.py`. It reads the sentence "The engines." of `k8s/README.md` and asserts that the names in backticks equal `keep_only`. It passes on the base, and it fails after task 1.2 until task 3.2 is done
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py -k readme_lists` passes on the base
- [x] 3.2 In the line "The engines." of `k8s/README.md`, change "ten engines" to "nine engines" and remove `pypi` from the list. Replace the sentence about `pypi` with a short statement that `pypi` is not kept, because `pypi.org` serves a Client Challenge page to a scraper and the engine returned no hit in the live check of 2026-11-07. Keep the sentence about the refusals of `github` and `duckduckgo`, and add that SearXNG suspends a refusing engine (CAPTCHA and access denied for 86400 s, too many requests for 3600 s), that `duckduckgo` raises its CAPTCHA with no suspension, and that the settings add no retry loop
  - Verification: `$ uv run devops ci test tests/invariants/test_k8s_searxng.py` passes
- [x] 3.3 Check the whole set of checks that read the ConfigMap and the README
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- #3929 holds the live check of SearXNG. This change does not touch its criteria.
- Pending a person: restart `deployment/searxng` after Argo CD syncs the ConfigMap, so that the pod reads the shorter engine list.
