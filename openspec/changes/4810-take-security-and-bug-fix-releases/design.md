# Design

## Decisions
- **The rule lives in `CONTRIBUTING.md`, section 1.** That section holds the rules for every contributor, and `AGENTS.md` sends code and setup work to it. The rule covers bug fixes and tool support, not only security, so `SECURITY.md` links to it and does not hold it.
- **The SearXNG steps apply the rule and link to it.** Step 1 of the pin in `k8s/README.md` names the test that limits the tag. The note in `.github/renovate.json` sends the person to those steps and does not repeat them.
- **A test guards the Renovate file.** The file sets no `minimumReleaseAge` today. A test fails if a later change adds one, or extends `config:best-practices`, which adds an npm age of 3 days.

## Rejected alternatives
- **Keep a shorter age, such as 3 days, for each update that is not a security fix.** The owner direction removes the age for all updates. A release with a bug fix has the same need as a security fix.
- **State the rule in `SECURITY.md`.** The rule covers bug fixes and tool support, which are not security subjects. One document holds the rule, so `SECURITY.md` only links to it.
