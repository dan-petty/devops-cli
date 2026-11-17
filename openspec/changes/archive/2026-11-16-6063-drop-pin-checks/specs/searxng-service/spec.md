## REMOVED Requirements

### Requirement: The settings keep only engines that need no key
**Reason**: Its scenarios compared the kept names and the names file with the pinned image. The owner decided on 2026-11-16 (#6060) that no test compares a file with the pinned image.
**Migration**: "The settings keep only keyless engines" holds the rest of the requirement.

### Requirement: A bump of the image tells the person what to check
**Reason**: The note named the engine names file, which is removed (#6063).
**Migration**: "A SearXNG bump updates like any other image" holds the note.

## ADDED Requirements

### Requirement: The settings keep only keyless engines
The settings SHALL keep, with `use_default_settings` and `engines.keep_only`, the engines `duckduckgo`, `wikipedia`, `github`, `stackoverflow`, `askubuntu`, `superuser`, `arxiv`, `mdn` and `docker hub`, and no other. They SHALL keep none of `brave`, `braveapi`, `google`, `bing`, `startpage`, `mojeek` and `qwant`.

#### Scenario: A suspended engine is kept
- **WHEN** a test reads `keep_only`
- **THEN** no kept name is a forbidden engine

### Requirement: A SearXNG bump updates like any other image
No test SHALL compare a file or a constant with the pinned SearXNG image. The Renovate rule of the image SHALL give the pull request a note that names `devops k8s searxng-check` and names no age of the tag.

#### Scenario: A bump of the image
- **WHEN** Renovate opens a pull request that moves the SearXNG image
- **THEN** its text names `devops k8s searxng-check`, and no test fails only because the image moved
