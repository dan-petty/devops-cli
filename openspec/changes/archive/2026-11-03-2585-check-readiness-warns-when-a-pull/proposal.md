# Proposal

## Why

Issue #2585: `CONTRIBUTING.md` section 4 limits the body of a pull request to 1,000 characters before the trailers, because the squash merge makes the body the commit message on `main`. Today only a reviewer enforces the limit. Agents write most bodies and run `devops pr check-readiness` before `devops pr ready`, so a warning there reaches the writer at the right time.

## What Changes

- `assess_merge_readiness` in `src/devops_cli/github/merge_readiness.py` adds one WARNING advisory when the body of the pull request, without its trailer lines, is longer than 1,000 characters. The advisory names the length, the limit and `CONTRIBUTING.md` section 4.
- The limit (`_PR_BODY_MAX_CHARS`) and the five trailer prefixes (`_TRAILER_PREFIXES`) are private constants of that module, beside the one function that reads them. The text of the advisory is a new field of `PRMessages` in `src/devops_cli/lang/en/messages.py`, as for `changed_files_unread`.
- The length is the number of characters left after the trailer lines go out and the whitespace at both ends is trimmed. A body of `null` counts as empty.
- `CONTRIBUTING.md` section 4 says that `devops pr check-readiness` warns on a longer body, in place of "A reviewer checks the length of the body."
- The spec `pr-merge-readiness` gets two ADDED requirements. A message of a devops command is observable, so the change carries a spec delta.
- `devops pr ready` and `devops pr monitor` read the same verdict but print no advisory, so they do not change.
- The change fits one pull request.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| 1,000 characters give no advisory, 1,001 give one WARNING that names 1,001, 1,000 and `CONTRIBUTING.md` | group 1 (tasks 1.1 and 1.2) |
| Trailer lines do not count | group 1 (tasks 1.1 and 1.2) |
| The exit code of `devops pr check-readiness` is the same with and without the advisory | group 1 (task 1.1, a row of the table in `tests/commands/test_pr.py`) |
| `CONTRIBUTING.md` section 4 names the advisory | group 2 |

No criterion waits for a person.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge-readiness`: ADDED "A long pull request body gets a warning" and "The body warning blocks nothing".

## Impact

- Code: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/lang/en/messages.py`.
- Documents: `CONTRIBUTING.md`, `openspec/specs/pr-merge-readiness/spec.md` (by archive).
- Tests: `tests/github/test_merge_readiness.py`, `tests/commands/test_pr.py`.

Code that the change reuses or keeps green:

- `_Verdict.warn`, `AdvisoryLevel.WARNING` and `Advisory` in `src/devops_cli/github/merge_readiness.py`: the advisory path that the issue names.
- `_render_merge_readiness` and `_emit_readiness_status` in `src/devops_cli/commands/pr.py`: they print each advisory and exit 1 only on a blocker, so the exit code needs no change.
- The helpers `_pr`, `_assess` and `_warning` of `tests/github/test_merge_readiness.py`, and the table `test_check_readiness_prints_the_verdict_and_exits_on_it` with its helper `_readiness` in `tests/commands/test_pr.py`. Every existing row has no `body` key and must still print no advisory.
- `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` (also 1,000) in `src/devops_cli/config/constants.py` is not reused: it shortens the text that the implement job writes, and it has another reader and another reason.

## Feasibility

Checked on 2026-11-01 against `origin/main` at `0d2d0723`.

- The body is in the verdict input. `fetch_pr_details` (`src/devops_cli/github/pr_monitor.py:419`) reads the REST payload of the pull request, and `uv run devops gh api repos/dan-petty/devops-cli/pulls/3082 --jq '.body|length'` prints `706`, so the payload holds `body`. The REST field is `null` for an empty body, so the code reads `pr_data.get("body") or ""`.
- The advisory path exists. `git grep -n "class AdvisoryLevel" -- src` prints `src/devops_cli/github/merge_readiness.py:68`, whose docstring says "no advisory changes an exit code". `_emit_readiness_status` in `src/devops_cli/commands/pr.py` takes only `verdict.blockers`, so a WARNING cannot change the exit code.
- Nothing else prints an advisory. `git grep -n "\.advisories" -- src` prints only `src/devops_cli/commands/pr.py:1449` (the `check-readiness` render): `pr ready` and `pr monitor` read the verdict and ignore its advisories.
- Nothing newer did the work. `git log origin/main --oneline --grep='#1803\|#2585'` prints only the plan commit and the #2586 commit that wrote the rule. `git grep -n "trailer" -- src` prints nothing: no trailer code exists. The sentence "A reviewer checks the length of the body." is in `CONTRIBUTING.md` section 4 (`git grep -c` prints 1). A search of the open issues for a body-length advisory returns only #2585.
- The problem is real but smaller than the issue says. A script over `git log origin/main --format=%b` (squash commits only, the five trailer prefixes removed, whitespace trimmed) counts 260 commits from 2026-10-25 to 2026-10-28, with a median of 1,210 characters and 155 longer than 1,000. The issue gives 188, 1,287 and 119, which count another set of commits. From 2026-10-29 to 2026-11-01 the script counts 275 commits, a median of 746 and 78 longer than 1,000. The premise holds: more than a quarter of the recent bodies are still too long.
- The trailer prefixes are a closed set. `.github/pull_request_template.md` has `Closes #<issue>` and `Change:`. `Co-authored-by:` is the attribution line of agent commits. `Fail-to-pass:` and `Signed-off-by:` are in the issue only.
- `git interpret-trailers` does not fit. With the body `Body text.`, a blank line, `Closes #12`, a blank line, and two more lines `Change: ...` and `Co-authored-by: ...`, `git interpret-trailers --parse` prints only the last two lines: it drops `Closes #12`, whose separator is `#`, and it reads only the last paragraph.

## Existing Tool Considered

No open tool checks the length of a pull request body. The `Semantic PR title` action checks only the title, commitlint checks commits (the squash merge discards the branch commits), and markdownlint checks line lengths, not a total. `git interpret-trailers` finds trailers, but it fails on `Closes #12` (see Feasibility). The change builds about 20 lines in the verdict module, one message and a few test rows: about 40,000 tokens to build, 5,000 tokens a year to keep, and under one hour. The advisory uses the existing advisory path, so it adds no new mechanism. The change deletes no code.
