# Proposal: #7328

## Why

The `Release` run of v0.223.0 failed on 2026-11-26 (#7328). release-please published the GitHub release, and the job `Upload Release Assets` then got HTTP 422 `Cannot upload assets to an immutable release`. `devops repos onboard` turns on immutable releases on purpose, so each later release fails the same way and gets no wheel, sdist or checksum file. v0.222.0, published before the setting, holds 3 files. v0.223.0 holds none and can take none. Immutable releases stay on.

## What Changes

- `release-please-config.json` sets `draft` and `force-tag-creation`. release-please creates the git tag, then the GitHub release as a draft.
- The job `Upload Release Assets` attaches the files to the draft and then publishes it, in one script. `bash -e` stops the script before the publication when the upload fails. The job keeps `contents: write` and `GITHUB_TOKEN`.
- The release feed of the roadmap Service leaves out a release with no publication time. GitHub gives `published_at: null` for a draft, and the feed refused the whole list for one such entry, so the row `release_comments` would fail for as long as a draft exists.
- `RELEASE_CYCLE.md` says how a release is published and how to finish a release that stays a draft. `docs/SDLC.md` and the status history of ADR 0013 agree.
- The change fits one pull request.
- The publication of a release and the rounds of the Service are observable, so the change carries spec deltas.

## Capabilities

### New Capabilities

- `release-publication`: the order in which the `Release` run creates, fills and publishes a release.

### Modified Capabilities

- `roadmap-release-comments`: a draft with no publication time stops no round.

## Impact

- Code: `src/devops_cli/roadmap/release_feed.py`.
- Workflow and configuration: `.github/workflows/release.yml`, `release-please-config.json`.
- Tests: `tests/roadmap/test_roadmap_release_comments.py`, `tests/support/fakes/github_repository.py`.
- Documents: `RELEASE_CYCLE.md`, `docs/SDLC.md`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`.
- The event `release` `published` comes from the publication by `GITHUB_TOKEN`, after the files are attached. The image jobs do not wait for it.
- A publication fails when the files under `.github/workflows/` on `main` differ from those of the release commit, because `GITHUB_TOKEN` cannot get the `workflows` permission. The release then stays a draft until a person publishes it.

## Feasibility

- The failure: the log of the `Release` run of v0.223.0 holds the HTTP 422 above.
- release-please-action at `45996ed1f6d02564a971a2fa1b5860e934307cf7` (v5.0.0) bundles release-please 17.6.0. Its schema holds `draft` and `force-tag-creation` for the root and for a package. With `forceTag`, `createRelease` of `src/github-api.ts` calls `git.createRef` for `refs/tags/<tag>` at the release commit, then creates the release with `draft: true`. The schema says that without the forced tag a draft has no tag, and release-please does not find the previous release.
- GitHub documentation, [Immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases): create a draft, attach all files, then publish.
- GitHub documentation, [Update a release](https://docs.github.com/en/rest/releases/releases#update-a-release): push access publishes a release; a target commit whose workflow files differ from the default branch also needs the `workflows` permission, which `GITHUB_TOKEN` cannot have.
- The feed defect: the new case of `tests/roadmap/test_roadmap_release_comments.py` fails on the base with `GitHub returned malformed releases`.
- Not proved before a real release run: the whole draft cycle on GitHub, the `sha` output of a release whose tag exists, and the delivery of the `published` webhook.

## Existing Tool Considered

release-please, which the project already uses (ADR 0013), covers the need with its options `draft` and `force-tag-creation`, and `gh release edit --draft=false` of the GitHub CLI publishes. The change writes no release logic of its own and deletes no internal code.
