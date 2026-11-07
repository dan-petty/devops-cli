# Design

## Decision

One workflow with one job. Three steps do the work, and the token of each step is the least that it needs.

1. **Mint** the release App token with `contents: write` and `pull-requests: write`. The workflow reads only its output `app-slug`, to name the author of the release pull request (`<slug>[bot]`).
2. **Pick** with `GITHUB_TOKEN` (read only). The module `devops_cli.release.merge_candidate` judges each pull request that has `autorelease: pending`, lowest number first, and stops at the first one that passes. It prints `number=` and `sha=`, or nothing.
3. **Merge** with the App token, only when the pick printed a number: `gh pr merge <number> --squash --match-head-commit <sha>`.

The module takes the names of the required checks from `GET /repos/{repo}/rules/branches/main`, not from a copy in code, so a change of the ruleset needs no change here. It reads the checks of the head of `main` and of the pull request with `read_check_runs`, which fails closed when a page cannot be read. The pure function `refusals(facts)` holds every guard, so each guard has an offline test. The reads are tested over the `github_api` fake.

Values reach each script through `env:`, never through `${{ }}` in `run:`. The checkout uses no credentials and no ref, so the job runs the default branch and no code of a pull request. The check of the label and the release configuration is a test, not a copy of text: `RELEASE_FILES` must equal the manifest, `CHANGELOG.md`, `pyproject.toml` and the extra files of `release-please-config.json`.

## Rejected Alternatives

- **Turn on GitHub auto-merge for each release pull request.** It merges as soon as the checks pass, so the cadence is not 6 hours. It also stays on when release-please pushes again, and it has no guard on files or labels. The owner asked for a 6 hour cadence.
- **Shell and `jq` in the workflow.** The project keeps logic in Python under `src/devops_cli` with tests. The urgent-fix step of #1966 is shell because it has one decision; this change has twelve guards.
- **A new `devops release` command.** ADR 0013 deleted a `devops release` group, and a command needs help text, a dry-run class and generated documentation. The image build already runs `python -m devops_cli.roadmap.runner_tools`, so a module with `main()` is the established way.
- **One token for read and merge.** It would give the pick step the write token, and the pick step runs project code. The read token has `contents`, `pull-requests` and `checks` read only. The App token may lack `checks: read`, and a new App permission is a change that only a person makes.
- **Merge from Python.** The merge needs the App token in the process that reads the repository. A separate step keeps the token out of that process and uses `gh`, which the release workflow already uses for the same merge.
- **A required check that was skipped counts as a pass.** GitHub's rules accept a skipped required check, but the owner asked for `success`, and the three required checks run on the release pull request. A skipped required check refuses the merge and a person decides.
- **A date or version in the title test.** The title test uses `packaging.version.Version`, a standard parser, and no regular expression. It predicts no version (ADR 0013).
- **Same concurrency group as `release.yml`.** The merge would queue behind a publish run of up to an hour. `--match-head-commit` already keeps a run from merging a commit that moved.
