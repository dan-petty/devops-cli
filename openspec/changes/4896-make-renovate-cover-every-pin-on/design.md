# Design

## Decisions
- Two layers. The preset holds what all 7 Service repositories share. `.github/renovate.json` holds the paths, the custom managers and the coupled groups of this repository. The global self-hosted config (#4905) holds the platform, the token and `allowedCommands`.
- Order of the package rules: the ecosystem groups, the patch schedule, the fast publishers on Monday, the approvals, the titles and labels (all in the preset), then the repository rules, with the coupled groups last. A later rule wins, so a coupled group takes its packages out of the ecosystem groups.
- A coupled group sets no update type, so a major or a minor of its pins also comes in one pull request. `separateMajorMinor` (on by default) keeps a major in its own branch.
- `python runtime` sets `separateMultipleMinor`, because one update that needs an approval holds its whole branch (`generate.js`: `upgrades.some(...)`). The new minor waits in `minor-3.<n>-python-runtime`, and the digest and patch updates go on.
- Titles: `commitMessageAction` `update` and `commitMessageTopic` `{{{depName}}}`. Two rules shorten the longest names: an action has no word `action`, and a devcontainer feature is `feature <last part>`. Alerts have no `[SECURITY]` suffix; the prefix `fix(deps):` and the label `type/security` mark them. The test builds the summary of each pinned dependency of the repository (more than 500) and of each group.
- The DCGM tag `<DCGM>-<exporter>-<variant>` uses a regex versioning on the exporter version, which is the chart version. The SearXNG tag ends in a commit hash, so a regex versioning ignores it; the docker versioning would read the hash as a suffix that must match and would propose no update.
- The attestation action moves to the commit of `v4.2.2`. The earlier pin was an untagged `main` commit with a wrong `# v2` comment, which Renovate cannot follow.
- Fail-to-Pass Check names the App login, as the plan check of `pr-title.yml` names `devops-cli-service[bot]`. A rule on `user.type == 'Bot'` would also skip the fix pull requests of the Service App.

## Rejected alternatives
- `config:best-practices`: it adds a minimum release age to npm, against the owner rule (CONTRIBUTING.md, Dependency Versions; #4810).
- `rebaseWhen: behind-base-branch` (the old value): it pushes every open update after each merge, and each push starts about 25 jobs against a cap of 20.
- One group per ecosystem for all update types: a Python 3.15 or Node 26 move would then hold the weekly updates of the same group behind an approval.
- The helm-values manager alone for the values tags: it reads an image only when the object holds `repository` and `tag`. Gitea, DCGM and Argo Workflows give only a tag, so custom managers read them.
- The `github-release-attachments` datasource for the gh download: it fits 11 of 20 binaries (measured for #4902), so #4902 adds one repin command for all.
