# Task: The Release Job Stops When Its Tag Already Exists on Another Commit (#1805)

**Issue**: [#1805](https://github.com/dan-petty/devops-cli/issues/1805)
**Scope**: scope/release
**Feasibility**: Release Orchestration run 39677745263, on the merge commit 1a8b26c0 of the v0.2.38 release pull request, read version 0.2.37 from `pyproject.toml`, which the cut had not yet changed. The "Create Git Tag" step found `v0.2.37` on 954914e2, printed "Tag v0.2.37 already exists." and the job went on. `softprops/action-gh-release` then replaced the three assets of the published v0.2.37 release (their `updated_at` is 21:19:09 UTC on 2026-10-21, `v0.2.36`'s are untouched), the DevContainer image job pushed, and the Service Image job was cancelled before it pushed the `v0.2.37` and `latest` tags. `release.yml` publishes the commit it runs on, so the tag must either be new or already on that commit. The image jobs `need` the release job, so a failed tag step stops them too.

## Description

- [x] The step "Create Git Tag" in `.github/workflows/release.yml` has three outcomes:
  - no tag: it creates and pushes the tag on the published commit;
  - the tag already on `$GITHUB_SHA`: it keeps it and goes on, so a rerun of the same release works;
  - the tag on another commit: it fails with an error naming both commits, before the release, its assets or the images are published.
- [x] `tests/test_workflow_contracts.py` runs the step's own script from `release.yml` in a throwaway clone with a bare `origin`, for the three outcomes. The tag-on-another-commit case fails at the base, where the script exits 0.
- A push to main that does not name a new version now fails this step. That is intended: such a push has nothing to publish.
- Pending a person: the assets of the published `v0.2.37` release and its image tags are rebuilt from the `v0.2.37` tag. Run 39677745263 replaced the assets and pushed the DevContainer image.
