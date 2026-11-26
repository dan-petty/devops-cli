# Release Cycle — devops-cli

This page is for the person who releases `devops-cli`. [release-please](https://github.com/googleapis/release-please) makes every release from `main`. On each push to `main` that opens or updates a release pull request, the release workflow turns on GitHub auto-merge with the release App token (#6851), and GitHub merges it when its checks pass. The workflow `release-merge.yml` also runs every 6 hours as a safety net when every guard holds ([Scheduled Merge](#scheduled-merge)), and a person can merge it at any time. release-please writes `CHANGELOG.md`, `.release-please-manifest.json` and the version lines, so nobody edits those by hand. Agents change the release workflow and its configuration only through ordinary pull requests.

## How the Release Pull Request Is Made

1. Every pull request into `main` has a [Conventional Commit](https://www.conventionalcommits.org/) title, and the squash commit takes it ([`CONTRIBUTING.md`](CONTRIBUTING.md)).
2. On each push to `main`, the `Release` workflow (`.github/workflows/release.yml`) runs [release-please-action](https://github.com/googleapis/release-please-action). It opens one release pull request, or updates the one that is open.
3. release-please derives the version from the titles merged since the last release. The release pull request holds that version, the new section of `CHANGELOG.md`, `.release-please-manifest.json` and the version lines of `pyproject.toml` and `uv.lock`.
4. The release pull request shows the same required checks as every pull request. It runs no test shard: its `Tests & Coverage` passes when `Tests & Coverage` passed in the push run of `main` that it is based on ([ADR 0014](docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md)). The job `Tests on Main` waits for that run to end.

## Scheduled Merge

The workflow `release-merge.yml` runs every 6 hours (`cron: "0 */6 * * *"`, 00:00, 06:00, 12:00 and 18:00 UTC) and on **Run workflow** in the Actions tab. It merges the release pull request with the squash method, and it merges nothing else. It never edits the pull request, the tag, `CHANGELOG.md` or a version.

The module `devops_cli.release.merge_candidate` reads the open pull requests that have the label `autorelease: pending`, and picks the first one, by number, that passes every guard. A run merges at most one pull request. A guard that fails gives a line in the log of the step `Pick the Release Pull Request`, and the next run tries again.

| Guard | What it checks |
| :--- | :--- |
| State | The pull request is open and is not a draft. |
| Origin | The release App opened it, from a `release-please--branches--main` branch of this repository into `main`. |
| Labels | It has `autorelease: pending` and does not have `hold-release`. |
| Title | The title is `chore(main): release <version>`. |
| Files | It changes only `.release-please-manifest.json`, `CHANGELOG.md`, `pyproject.toml` and `uv.lock`, and it adds, removes and renames none of them. The guard reads the files from the compare of `main` and the head commit, which is the diff that the squash merge applies. It does not read the file list of the pull request, because that list can hold files of `main` after the merge base moved. |
| Checks | Every check that the ruleset of `main` requires passed on its head commit. No other check failed there, because the publish jobs of the release run the same scans. |
| `main` | No required check failed on the head of `main`. |
| Mergeable | GitHub reports it as mergeable. |

A failed read of GitHub fails the run, so a failed read does not look like a refusal. When a pull request passes, the step `Merge the Release Pull Request` runs `gh pr merge --squash --match-head-commit <sha>` with the release App token. If release-please pushed to the pull request after the pick, the merge fails and the next run judges the new commit. The App token merges, because a merge that `GITHUB_TOKEN` makes starts no workflow, and then no run creates the release. The token holds only `contents: write` and `pull-requests: write`, and only the merge step gets it.

To hold a release, set the label `hold-release` on the release pull request. The schedule skips it until a person removes the label. To turn the schedule off, open `release-merge.yml` under **Actions** and choose **Disable workflow**.

Each merge makes a release, and each release builds the images that Argo CD Image Updater moves onto the cluster ([What the Merge Publishes](#what-the-merge-publishes)). The schedule allows up to 4 releases a day.

## Merge by Hand

A person can merge the release pull request at any time, and must do so when a guard keeps the schedule from merging it.

1. Open the release pull request. Its title names the version.
2. Read the version and the new changelog section. Make sure that they agree with what merged.
3. Make sure that all required checks pass.
4. Squash-merge the pull request in the GitHub web UI.

## Automatic Merge

On each push to `main` that opens or updates a release pull request, the step `Enable auto-merge on the release pull request` of `release.yml` turns on auto-merge with the release App token (#6851). GitHub merges it when the required checks and the rules of the `main` ruleset pass. If they already passed, GitHub merges it at once. The App token does it, because a merge that `GITHUB_TOKEN` makes starts no workflow, and then no run creates the release.

The scheduled workflow `release-merge.yml` also runs every 6 hours as a safety net ([Scheduled Merge](#scheduled-merge)), and a person can merge at any time. To stop an automatic release, turn off auto-merge in the release pull request (**Disable auto-merge** in the GitHub web UI) before its checks pass, or set the label `hold-release`.

## What the Merge Publishes

The `Release` run of the merge creates the tag and the GitHub release as a draft (`draft` and `force-tag-creation` in `release-please-config.json`). The repository has immutable releases, which `devops repos onboard` turns on: a published release takes no more files, and its tag cannot move. So `Upload Release Assets` attaches the files to the draft and then publishes it, in one step. The image jobs do not wait for the publication. Then these jobs publish:

| Job | Publishes |
| :--- | :--- |
| `Upload Release Assets` | The wheel, the sdist and `SHA256SUMS.txt`, attached to the draft release, and then the release itself |
| `Build DevContainer Image`, `Smoke-Test DevContainer Image`, `Attest & Tag DevContainer Image` | `ghcr.io/dan-petty/devops-cli/devcontainer`, tagged with the release tag and `latest` |
| `Service Image / Build`, `Service Image / Verify`, `Service Image / Attest & Tag` | `ghcr.io/dan-petty/devops-cli/service`, tagged with the release tag and `latest` |
| `Runner Image / Build`, `Runner Image / Verify`, `Runner Image / Attest & Tag` | `ghcr.io/dan-petty/devops-cli/runner`, the image of the implement Job, tagged with the release tag and `latest` |
| `MCP Server Image / Build`, `MCP Server Image / Verify`, `MCP Server Image / Attest & Tag` | `ghcr.io/dan-petty/devops-cli/mcp-server`, the image of Deployment `mcp-server`, tagged with the release tag and `latest` |

The `Build` job of an image builds the image one time and pushes it by digest, with no tag. The `Verify` job pulls that digest, builds the stage of the image in [`smoke.Dockerfile`](smoke.Dockerfile) on it, runs the checks that need a container, and scans it. The `Attest & Tag` job attests the digest, puts the release tag and `latest` on it, and checks that each tag names that digest. Each image goes through its own three jobs of [`release-image.yml`](.github/workflows/release-image.yml), so a failed job of one image stops no job of another image. A digest that fails `Verify` gets no tag, and Image Updater reads only `latest`, so that digest reaches no cluster.

Argo CD Image Updater then moves the Service, the CronJob templates of the runner image and Deployment `mcp-server` onto the new image digests ([`docs/CLUSTER.md`](docs/CLUSTER.md#service-image-updates), Service Image Updates).

## When a Publish Job Fails

1. Open the failed `Release` run in the **Actions** tab of the repository.
2. Read the log of each failed job.
3. If the cause is outside the repository, such as a registry outage, click **Re-run failed jobs**. The jobs that passed keep their results. A re-run of a `Verify` job pulls and scans the same digest again.
4. If the scan of an image finds a vulnerability that a new package outside the repository fixes, open the `Build` job of that image and re-run that job. GitHub also re-runs the `Verify` and `Attest & Tag` jobs of the image, so the new build takes the new packages and `Verify` scans the new digest. Do not use **Re-run all jobs**: release-please then runs again, finds no release to create, and each image job skips.
5. If the cause is in the repository, fix it in a pull request into `main`. The fix ships in the next release.

### A Release That Stays a Draft

A release stays a draft when `Upload Release Assets` fails, or when `Release Please` fails after it created the draft. The tag exists in both cases. Until the publication, the release is not the latest release and the roadmap Service comments no `Released in <tag>`.

When `Release Please` fails, the run builds no package file and no image, because each publish job needs that job. Look at the labels of the release pull request:

- With the label `autorelease: pending`, each `Release` run tries the release again. Delete the draft, which keeps the tag, and then click **Re-run failed jobs**. The re-run creates the draft again and runs the publish jobs. With no deletion, a second draft for the same tag can result.
- Without that label, no run creates this release again. Publish the draft by hand (step 2). This version gets no image, and the next release ships the changes in its images.

When only `Upload Release Assets` fails, the images do not depend on it.

1. If no newer release is published, click **Re-run failed jobs**. The upload replaces the files that the draft already holds, and the job then publishes. A re-run uses the workflow file of the failed run, so a later fix of the workflow does not apply to it. Never use **Re-run all jobs**: release-please finds no release to create, so the job skips.
2. Publish the draft by hand, in the GitHub web UI under **Releases**, when no re-run can publish it, or when a newer release is published. After the publication, no file can be added or replaced. If the upload of the last run passed, publish the files as they are. If not, make all three files from one build: delete each file that the draft holds, check out the tag, run `uv build --clear`, run `cd dist && sha256sum -- * > SHA256SUMS.txt`, and attach the wheel, the sdist and `SHA256SUMS.txt`. Without `--clear`, `dist/` can keep old builds, and the checksum file lists them. When a newer release is published, clear **Set as the latest release**.
3. The publication can fail with HTTP 403 or 404 when the files under `.github/workflows/` on `main` differ from those of the release commit. GitHub then asks for the `workflows` permission, which `GITHUB_TOKEN` cannot have ([Update a release](https://docs.github.com/en/rest/releases/releases#update-a-release)). A re-run fails the same way, so publish by hand.

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
