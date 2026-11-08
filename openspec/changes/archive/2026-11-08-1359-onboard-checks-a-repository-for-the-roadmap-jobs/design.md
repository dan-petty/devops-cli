# Design

## Decisions

- **Extract `declared_type_labels` into `src/devops_cli/roadmap/title_labels.py`**: Both intake and onboard require the rule that extracts `type/*` labels other than `type/epic`. A single function keeps the rule in one place.
- **Implement onboarding logic in `src/devops_cli/roadmap/onboard.py`**: Keeping `check_onboarding` and `apply_onboarding` separate from command rendering allows the roadmap Service to call the checks in a future change.
- **Implement a thin command in `src/devops_cli/commands/roadmap.py`**: Keeps all roadmap command CLI definitions colocated in `commands/roadmap.py`.
- **Row 1 prints the PATCH command and never sends PATCH**: Setting repository configuration is a human administrative operation, and the GitHub App token has no repository administration permissions.
- **Row 2 checks `acts_as_github_app()`**: When the process acts as the App, paginate `/installation/repositories` to check installation. When running as a person, report `not readable as <login>` because GitHub provides no endpoint to inspect an App installation using a person's token.
- **Row 4 is not readable when Row 3 is not present**: When the labels specification file is missing or invalid, no label diff can be calculated, so missing labels cannot be asserted.
- **Row 4 creates only missing labels with POST**: Onboarding must never overwrite or delete labels configured by repository owners. Differing labels are noted as kept.
- **Row 6 prints configuration steps without writing `config.yaml`**: Modifying configuration files is reserved for repository owners according to project invariants.
- **Dry run uses `request_plan.py`**: `onboard_requests` returns the planned reads and writes, rendered via `render_dry_run` with placeholders.

## Rejected alternatives

- **Send the PATCH request for issues directly**: Rejected. Repository settings are reserved for human operators, and the App token has no administration scope.
- **Query `/repos/{owner}/{repo}/installation` or `/user/installations` with a user token**: Rejected. GitHub REST endpoints return HTTP 401 or 403 when called without App authentication.
- **Use external label sync tools**: Rejected. External tools synchronize by modifying and deleting labels, which breaks the invariant that human-created labels are preserved.
- **Mark Row 4 missing when Row 3 is invalid**: Rejected. Reporting row 4 as missing would report a defect that no successful read established.
- **Put shared type rules in `onboard.py`**: Rejected. Intake would then import onboarding modules for general label parsing.
