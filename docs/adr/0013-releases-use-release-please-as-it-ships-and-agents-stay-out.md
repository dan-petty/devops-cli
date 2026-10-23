# Releases use release-please as it ships, and agents stay out of them

ADR 0013 supersedes [ADR 0012](0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md).

ADR 0012 adopted release-please, but it put a custom design around the tool. That design had a draft release, a publish order through `softprops/action-gh-release`, a tag ruleset as the production gate and Argo CD on semver tags. It also had a cutover of thirteen steps, a rehearsal of ten premises, a `Release-As` path and estimates of future versions. It kept the roadmap planner and gave it date-titled buckets. Agents misread the bespoke release path again and again: wrong pull request titles and bases, stacked pull requests and a republished version.

On 2026-10-23 the owner decided to keep agents as far from the release workflow as possible, because open tools already do it well. The owner also said: "Do not attempt to anticipate the release workflow versioning or make that part of the new workflow." Every instruction that conflicts with this decision is deleted.

## Decision

- **The tool makes every release.** `.github/workflows/release.yml` runs `googleapis/release-please-action` on each push to `main`, in manifest mode with the `python` release type. It opens or updates one release pull request. A person merges that pull request. The run of that merge creates the GitHub release and its tag.
- **The same run publishes.** When the action reports a new release, later jobs upload the wheel, the sdist and `SHA256SUMS.txt` to that release. Other jobs build, smoke-test, attest and tag the two images with the release tag and `latest`. There is no draft release and no extra publish order.
- **A GitHub App token runs the action.** A pull request that `GITHUB_TOKEN` opens starts no workflow, so the release pull request needs the App token to run its checks. The token has contents, issues and pull requests write. The `release` environment holds the App client ID and private key.
- **The version comes from the tool.** `release-please-config.json` sets `bump-minor-pre-major` and sets nothing else that steers a version. No code, test, document or setting in this repository predicts, computes or checks a future version.
- **The pull request title is the changelog line.** Each title is a Conventional Commit, and the `Semantic PR title` check enforces it. The squash commit takes the title.
- **Agents take no part in a release.** Agents do not open, edit, review, comment on or merge the release pull request. Agents do not create tags or releases, and do not edit `CHANGELOG.md`, the manifest or version lines. Agents never write a `Release-As:` line.
- **Argo CD keeps tracking `main`.** The applications do not follow tags, and the tag flip of [#1862](https://github.com/dan-petty/devops-cli/issues/1862) is not done.
- **The roadmap planner is deleted.** `devops roadmap reprioritize`, `close`, `render` and `migrate`, the document writer and `docs/ROADMAP.md` are deleted. Intake puts each new item in the backlog. A milestone is a planning bucket that a person sets, and no code reads its title as a version.
- **The bespoke release path is deleted.** Release branches, the cut, changelog fragments, `Part of #N`, the release notes tooling and `devops release` are gone. Each topic pull request targets `main` and closes one issue.
- **The OpenSpec archive stays where ADR 0010 puts it**: in the pull request that closes the issue.

## Consequences

- A person releases by merging the release pull request. There is no schedule. [`RELEASE_CYCLE.md`](../../RELEASE_CYCLE.md) is the procedure.
- A person keeps the repository settings that the tool needs: the App, the `release` environment, the squash title and body, and the required checks ([#1864](https://github.com/dan-petty/devops-cli/issues/1864)).
- The changelog holds titles only. The long entries of the old fragments are not kept.
- Because Argo CD tracks `main`, a tag deploys nothing. A tag ruleset is optional.
- The first release that release-please makes is examined after it exists ([#1865](https://github.com/dan-petty/devops-cli/issues/1865)). Nobody predicts its version.
