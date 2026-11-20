## MODIFIED Requirements

### Requirement: The settings keep only keyless engines
The settings SHALL keep, with `use_default_settings` and `engines.keep_only`, the engines `duckduckgo`, `wikipedia`, `github`, `arxiv`, `mdn` and `docker hub`, and no other. They SHALL keep none of `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek`, `qwant`, `stackoverflow`, `askubuntu` and `superuser`.

#### Scenario: A suspended engine is kept
- **WHEN** a person runs `uv run devops k8s searxng-check`
- **THEN** no reply holds a hit of an engine that must stay off, no unresponsive engine list names one, and the command exits 0

#### Scenario: A Stack Exchange engine that must stay off fails the check
- **WHEN** a reply of `uv run devops k8s searxng-check` names `stackoverflow`, `askubuntu` or `superuser` among its results or its unresponsive engines
- **THEN** the row reports that the engine must stay off and the command exits 1
