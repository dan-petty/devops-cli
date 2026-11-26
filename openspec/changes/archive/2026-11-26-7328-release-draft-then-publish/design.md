# Design

## Decisions

- **release-please creates a draft and its tag.** `draft` alone gives no git tag before the publication. The image jobs, the next run of release-please and each reader of tags need the tag at once, so `force-tag-creation` goes with it.
- **The job that attaches the files publishes.** It is the one job whose work must be on the release before it is locked. The image jobs push to the registry and read only the tag name and the commit, so they keep their place beside it.
- **One script holds the order.** The upload and the publication are two commands of one `run` step. The default shell of Actions on Linux is `bash -e`, so a failed upload ends the step. No condition between steps can be lost in an edit.
- **`GITHUB_TOKEN` publishes.** The job already has `contents: write`, which publishes a release. The job runs `uv build`, so it gets no App key.
- **The step has no draft check for a second run.** A run of the step on a published release fails on the upload with HTTP 422 and changes nothing.
- **The feed leaves out a release with no publication time.** Such a release is not out, and no reader of the feed wants it. `ReleaseInfo.published_at` keeps its type, so no reader of the window handles an absent time. The feed is the one reader of the release list that needs the time: `git grep -n 'releases?per_page\|repos/{repo}/releases' -- src` also finds `project_review/catalog.yaml`, which drops drafts and uses `created_at`, and `project_review/readiness.py`.
- **ADR 0013 gets a status line.** Its body says that there is no draft release. The body of an accepted record does not change, so the line has the form `Fact out of date`. It cites #7328 and claims no decision that #7328 does not record. docs/adr/README.md says that the next change supersedes a record whose body contradicts the code. This change does not write that record: the next change of ADR 0013 does.

## Rejected alternatives

- **Turn immutable releases off.** `devops repos onboard` turns the setting on (`src/devops_cli/github/onboard/settings_rows.py:336`). It protects the files and the tag of a release against a change.
- **`draft` with no `force-tag-creation`.** The schema of release-please 17.6.0 says that GitHub creates no tag for a draft, and that release-please then fails to find the previous release.
- **A publish order of our own, or `softprops/action-gh-release`.** ADR 0013 deleted that design (`docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`, first section). The options of release-please need no extra action.
- **Publish with the release App token.** The App token of `release.yml` asks for `contents`, `issues` and `pull-requests`, not `workflows`. The change would need a permission that only the owner can give, and the App key in a job that builds the packages. It removes the one case where the publication needs `workflows`, so it stays open if that case occurs.
- **Publish after the image jobs.** A failed image would keep the release a draft, and `Released in <tag>` would wait for the slowest of 5 images.
- **A test that reads `release.yml` for the order.** docs/TESTING.md gives a workflow no test, and the row `test-tree` refuses a new test that reads a file under `.github` (`tests/gate/tree_checks/config_values.py`, `CONFIG_ROOTS`). The proof is `actionlint`, `zizmor` and the live check of the spec.
