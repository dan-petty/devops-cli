# Proposal: #4686

## Why

No command reviews a version range or a period (#4686). `devops gh metrics` selects releases by count (`--limit 10`), and the repository has 275 `v*` tags. Tag times use mixed time zones: `v0.112.1` has the creator date `2026-11-11T07:51:23-07:00` and `v0.111.0` has `2026-11-11T05:38:00Z`, so a compare of the time strings gives the wrong set. PyDriller and git disagree at the edges of a range (38 against 37 commits). A count of commits for each path breaks on a rename: `roadmap/stage_change.py` had 13 commits at its old path and 36 at its new path in one week.

## What Changes

- Add `devops roadmap review run` with `--version A..B`, `--since` with `--until`, `--week YYYY-Www`, `--last Nd`, `--repo`, `--out`, `--json` and `--dry-run`, in the new package `src/devops_cli/roadmap/project_review/`.
- The window resolver makes each window two first-parent commits and two aware UTC times. The window is half-open: the base commit and the start time are out, and the head commit and the end time are in. Each window has an id that is safe for a path and a key (`v0.111.0..v0.112.1`, `2026-W45`, `20261104T1451Z..20261111T1451Z`) and names the window before it, of the same kind and length.
- The git reader runs `git log --first-parent -M --numstat -z`, `git diff -M --numstat -z`, `git check-attr linguist-generated` and `git for-each-ref` with `creatordate:unix`. The facts are the commits, their Conventional Commit types (through `roadmap/commit_title.py`), the net change and the churn with the generated paths apart, the release tags, the hot files with their renames followed, and the lizard complexity of the hottest files at the base and at the head.
- The command writes `data.json` and its JSON Schema `data.schema.json`. Each fact has an id, a value, a unit, `n`, a source, the exact query, a definition, `read_at`, and a status (`ok`, `expired`, `skipped` or `error`) with a reason.
- `--dry-run` starts no program and opens no connection: it prints the git commands of a run with a placeholder for each value that a read gives.
- A new optional extra `review` holds lizard 1.24.3 (MIT). `uv sync --all-groups --all-extras` (the dev setup and CI), the devcontainer image and the Service image install it (owner decision of 2026-11-11). Without lizard, the complexity fact is `skipped` with a reason.
- `.gitattributes` marks the generated files (`uv.lock`, `package-lock.json`, `CHANGELOG.md`, the release manifest and the generated command reference) `linguist-generated`, so the review counts their lines apart and GitHub folds their diffs.
- The command is a new observable behavior, so the change adds the capability `roadmap-project-review`.

## Capabilities

- `roadmap-project-review` (new): the window of a project review, its git facts and `data.json`.

## Impact

- New command `devops roadmap review run` and the new error `RoadmapReviewError` (`ROADMAP_REVIEW_FAILED`).
- New dependency: lizard 1.24.3 (MIT) in the optional extra `review`. The images and the CI sync install it.
- The command reads the local checkout only. It sends no request to GitHub or to another service.
- The change fits one pull request.

## Feasibility

- git 2.55.0 on this repository: `git for-each-ref --format='%(refname:short) %(creatordate:iso-strict)' refs/tags/v0.111.0 refs/tags/v0.112.1` gives `2026-11-11T05:38:00Z` and `2026-11-11T07:51:23-07:00`. `creatordate:unix` gives the instant, so the compare is correct.
- The command on this repository gives the facts of the acceptance criteria. `--version v0.111.0..v0.112.1` gives 37 commits, 421 files, a net change of +14,553/-1,600, and the 2 releases `v0.112.0` and `v0.112.1`, with `v0.111.0` out. `--since 2026-11-04T14:51:23Z --until 2026-11-11T14:51:23Z` gives 545 commits and 111 tags (57 minor, 54 patch), with `v0.55.4` in. The hot-file row of `src/devops_cli/roadmap/stage/stage_change.py` gives 49 commits (13 at the old path and 36 at the new path) and names the old path.
- The 7-day collection took 9.7 s, under the 15 s limit.
- lizard 1.24.3 reads source text through `lizard.analyze_file.analyze_source_code(path, text)` and gives the cyclomatic complexity of each function, so the review reads each blob with `git cat-file blob` and changes no file of the checkout.

## Existing Tool Considered

- git covers the window and the change facts through its standard commands. lizard 1.24.3 (MIT) covers the complexity. pydantic covers the model and its JSON Schema. `packaging` gives the kind of each release version.
- PyDriller is rejected: it disagrees with git at the edges of a range (38 against 37 commits).
- The custom code is the window resolver and one thin git reader, about 750 lines with tests. Cost: about 0.33 to 0.50 USD of model tokens to build on the DeepSeek implement path, a small cost to keep because each reader is one git command, and 1 to 2 days elapsed.
- The change deletes no internal code: no command reads a version range or a period today.
