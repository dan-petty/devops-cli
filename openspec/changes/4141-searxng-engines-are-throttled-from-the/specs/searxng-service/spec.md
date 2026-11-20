## MODIFIED Requirements

### Requirement: The settings keep only keyless engines
The settings SHALL keep, with `use_default_settings` and `engines.keep_only`, the engines `duckduckgo`, `wikipedia`, `github`, `arxiv`, `mdn` and `docker hub`, and no other. They SHALL keep none of `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek`, `qwant`, `stackoverflow`, `askubuntu` and `superuser`.

#### Scenario: A suspended engine is kept
- **WHEN** a person runs `uv run devops k8s searxng-check`
- **THEN** no reply holds a hit of an engine that must stay off, no `unresponsive_engines` list names one, and the command exits 0

#### Scenario: The settings render with the six kept engines
- **WHEN** a person runs `uv run devops ci --check --only k8s` over `k8s/devops/searxng/configmap.yaml`
- **THEN** the render succeeds, and the settings name the six kept engines and none of the ten engines that must stay off

#### Scenario: The general category holds a hit
- **WHEN** a person runs `uv run devops k8s searxng-check` on the cluster after the rollout of `k8s/devops/searxng/configmap.yaml`
- **THEN** the row of the general category holds at least one hit, and the command exits 0
