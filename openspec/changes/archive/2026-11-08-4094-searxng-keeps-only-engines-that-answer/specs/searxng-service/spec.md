## MODIFIED Requirements

### Requirement: The settings keep only engines that need no key
The settings SHALL keep, with `use_default_settings` and `engines.keep_only`, the engines `duckduckgo`, `wikipedia`, `github`, `stackoverflow`, `askubuntu`, `superuser`, `arxiv`, `mdn` and `docker hub`, and no other. They SHALL keep none of `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek` and `qwant`. They SHALL keep no engine that `tests/fixtures/searxng/engines_that_never_answer.txt` lists, and each line of that file SHALL give a date and a reason. Every kept name SHALL be an engine name in the default settings of the pinned image. The list of engines in `k8s/README.md` SHALL name the same engines as `keep_only`.

#### Scenario: A suspended engine is kept
- **WHEN** a test reads `keep_only` and the engine names file of the pinned image
- **THEN** no kept name is a forbidden engine, and every kept name is in the names file

#### Scenario: A bump leaves the names file behind
- **WHEN** a test compares the tag in the first line of the names file with the tag of the Deployment
- **THEN** the tags are the same

#### Scenario: An engine that never answers is kept
- **WHEN** a test reads `keep_only` and `tests/fixtures/searxng/engines_that_never_answer.txt`
- **THEN** no kept name is in that file, the first name in that file is `pypi`, each line has a date and a reason, and every name is an engine of the default settings

#### Scenario: The README lists other engines than the settings
- **WHEN** a test reads the sentence "The engines." of `k8s/README.md` and `keep_only`
- **THEN** the names in backticks in the sentence equal the names in `keep_only`

## ADDED Requirements

### Requirement: The ConfigMap explains the two log lines of the start
The file `k8s/devops/searxng/configmap.yaml` SHALL hold a comment, outside the text of `settings.yml`, that names the ERROR "X-Forwarded-For nor X-Real-IP header is set!" with its source `searx/botdetection/trusted_proxies.py`, and the WARNING for a missing `limiter.toml` with its source `searx/botdetection/config.py`, and that says both are harmless with the limiter off.

#### Scenario: The comment is missing
- **WHEN** a test reads the text of `k8s/devops/searxng/configmap.yaml`
- **THEN** the text names `X-Forwarded-For`, `searx/botdetection/trusted_proxies.py`, `limiter.toml`, `searx/botdetection/config.py` and the word "harmless"
