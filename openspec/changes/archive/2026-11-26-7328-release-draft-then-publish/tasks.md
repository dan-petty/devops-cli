# Tasks

## 1. A draft stops no round of the release comments

Kind: behavior. Reads: `src/devops_cli/roadmap/release_comments.py`. Changes: `src/devops_cli/roadmap/release_feed.py`, `tests/roadmap/test_roadmap_release_comments.py`, `tests/support/fakes/github_repository.py`.

- [x] 1.1 Let `GitHubFake.seed_release` take no publication time, and add the case `test_a_draft_with_no_publication_time_stops_no_comment_of_the_round`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_release_comments.py` fails on the base
- [x] 1.2 Leave out of `GitHubReleaseFeed.releases` each release with no publication time
  - Verification: `$ uv run devops ci test tests/roadmap` passes

## 2. Publish a release after its files are attached

Kind: other. Changes: `release-please-config.json`, `.github/workflows/release.yml`.

- [x] 2.1 Set `draft` and `force-tag-creation`, and publish the draft after the upload in the step of the job `Upload Release Assets`
  - Verification: `$ uv run devops ci --check --only actionlint --only zizmor`

## 3. Documents

Kind: other. Changes: `RELEASE_CYCLE.md`, `docs/SDLC.md`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`.

- [x] 3.1 Describe the draft, the publication and a release that stays a draft, and add the status line to ADR 0013
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- v0.223.0 stays with no files: a published immutable release takes none.
- Pending a person: after the next release, check that `devops gh api repos/dan-petty/devops-cli/releases/latest --jq '[.draft, .immutable, (.assets | length)]'` gives `[false,true,3]`, that each job of its `Release` run passed, and that its closed issues hold `Released in <tag>`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
