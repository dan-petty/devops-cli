# Design

## Decisions

- **Add a dated ignore entry to `.trivyignore.yaml`**: The file is installed by the harbor package and is not part of the committed source code. SECURITY.md requires a time-limited ignore entry with an expiry date for unfixable external files.
- **Set expiry to 3 days from creation**: SECURITY.md sets an expiry of 3 days for initial entries, with renewals up to 14 days.

## Rejected alternatives

- **Edit the virtualenv file**: The file is reinstalled whenever dependencies update.
- **Dismiss the alert on GitHub**: Dismissing on GitHub leaves no record in git history.
