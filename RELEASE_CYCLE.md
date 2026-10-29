# Release Cycle — devops-cli

This page is for the person who releases `devops-cli`. [release-please](https://github.com/googleapis/release-please) makes every release from `main`, and a person merges its pull request. For an urgent fix, GitHub merges the release pull request when its checks pass ([Urgent Fixes](#urgent-fixes)). release-please writes `CHANGELOG.md`, `.release-please-manifest.json` and the version lines, so nobody edits those by hand. Agents change the release workflow and its configuration through ordinary pull requests ([`AGENTS.md`](AGENTS.md)).

## How the Release Pull Request Is Made

1. Every pull request into `main` has a [Conventional Commit](https://www.conventionalcommits.org/) title, and the squash commit takes it ([`CONTRIBUTING.md`](CONTRIBUTING.md)).
2. On each push to `main`, the `Release` workflow (`.github/workflows/release.yml`) runs [release-please-action](https://github.com/googleapis/release-please-action). It opens one release pull request, or updates the one that is open.
3. release-please derives the version from the titles merged since the last release. The release pull request holds that version, the new section of `CHANGELOG.md`, `.release-please-manifest.json` and the version lines of `pyproject.toml` and `uv.lock`.
4. The release pull request runs the same required checks as every pull request.

## Merge the Release Pull Request

A person decides when to release, except for an urgent fix ([Urgent Fixes](#urgent-fixes)). There is no schedule.

1. Open the release pull request. Its title names the version.
2. Read the version and the new changelog section. Make sure that they agree with what merged.
3. Make sure that all required checks pass.
4. Squash-merge the pull request in the GitHub web UI.

## Urgent Fixes

An urgent fix releases without a wait for a person. After `Run release-please` updates the release pull request, the step `Merge the Release Pull Request on an Urgent Fix` of `release.yml` reads the pull request of the pushed commit and the issues that it closes. The fix is urgent when one of these is true:

- The pull request has the label `release-now`. A person sets this label.
- An issue that it closes has the label `priority/p0-critical`.
- An issue that it closes has the labels `type/security` and `priority/p1-high`.

For an urgent fix, the step turns on auto-merge of the release pull request with the release App token. GitHub merges it when the required checks and the rules of the `main` ruleset pass. If they already passed, the step merges it at once. The App token does it, because a merge that `GITHUB_TOKEN` makes starts no workflow, and then no run creates the release. For any other pull request, the step does nothing, and a person merges the release pull request.

To stop an automatic release, turn off auto-merge in the release pull request (**Disable auto-merge** in the GitHub web UI) before its checks pass.

## What the Merge Publishes

The `Release` run of the merge creates the GitHub release and its tag. Then these jobs publish:

| Job | Publishes |
| :--- | :--- |
| `Upload Release Assets` | The wheel, the sdist and `SHA256SUMS.txt`, attached to the GitHub release |
| `Build DevContainer Image`, `Smoke-Test DevContainer Image`, `Attest & Tag DevContainer Image` | `ghcr.io/dan-petty/devops-cli/devcontainer`, tagged with the release tag and `latest` |
| `Build & Publish Service Image` | `ghcr.io/dan-petty/devops-cli/service`, tagged with the release tag and `latest` |

Argo CD Image Updater then moves the Service onto the new image digest ([`k8s/README.md`](k8s/README.md), Service Image Updates).

## When a Publish Job Fails

1. Open the failed `Release` run in the **Actions** tab of the repository.
2. Read the log of each failed job.
3. If the cause is outside the repository, such as a registry outage, click **Re-run failed jobs**. The jobs that passed keep their results.
4. If the cause is in the repository, fix it in a pull request into `main`. The fix ships in the next release.

## Versioning Policy

### Pre-1.0 Alpha Lifecycle & Zero Backwards Compatibility Guarantee
`devops-cli` is active **alpha software** prior to release `1.0.0`:
- **Zero Backwards Compatibility Guarantee**: Until at least release `1.0.0`, there is **no intention of maintaining backwards compatibility**. Breaking changes, interface evolutions, parameter alterations, and schema redesigns may occur across any release cycle without legacy shims.
- **Zero Legacy Remnants**: The codebase must remain clean of legacy references, obsolete shims, deprecated aliases, and vestigial fallback paths at all times so that it can reach architectural maturity at a reasonable rate.
- **Clean Solutions Over Zombie Code**: Features and interfaces are designed cleanly for current and future needs rather than burdened with compatibility workarounds.

### Post-1.0 Semantic Versioning & Enterprise Change Management
Any version released after `1.0.0` will strictly adhere to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) (`MAJOR.MINOR.PATCH`):
- **MAJOR (`X.0.0`)**: Incompatible API or breaking CLI command syntax changes.
- **MINOR (`X.Y.0`)**: Backward-compatible new functionality (e.g., new subcommands, security scanners, or FastMCP tools).
- **PATCH (`X.Y.Z`)**: Backward-compatible bug fixes, performance optimizations, or prompt refinements.
- **Change Management Best Practices**: Post-1.0 releases will utilize all enterprise change management mechanisms, including runtime feature flags, structured multi-release deprecation warnings (emitted for at least one minor release cycle before removal), and automated migration tooling.

The decision record is [ADR 0013](docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md).
