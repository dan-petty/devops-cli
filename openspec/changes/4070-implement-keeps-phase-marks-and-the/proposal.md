# Proposal

## Why

An implement Job repeats work and loses facts after a kill or a continuation (#4070). The Service starts a continuation Job when a Job ends with no result (#3721), and #3677 now keeps each passed group on origin. Four faults remain.

1. Every Job runs `_pull_request`, which calls `_comment(pull, _NOTHING_YET)`. A continuation Job that finds all groups ticked has no outcome of its own, so it posts a comment with the body `-` and no table. The table of the earlier Job stays in the older comment, but the new comment has no content, and a reader cannot tell which comment belongs to which run.
2. The scoped checks (about 3.5 minutes) run again in every Job, also at a head that already passed them.
3. `implement.spend` is written only at a stop and at ready, and only with the spend of the last Job. A killed Job leaves no spend. A continuation starts with a full item budget, so an item with two continuations can spend three budgets. At a stop, the record keeps the spend of the last Job and drops the earlier ones.
4. The wait for the checks of the pull request runs up to 3600 s and writes no line to the log of the Job.

## What Changes

- Add `CHECKED_SHA` (`implement.checked_sha`) and `PUBLISHED_SHA` (`implement.published_sha`) to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py`. `_push` writes `checked_sha` with the head after the scoped checks pass, and `published_sha` with the head after the push. A Job whose head equals `checked_sha` skips the scoped checks. A Job whose head equals `published_sha` skips the push. A fix step or a rebase that moves the head makes both marks stale, so the checks and the push run again. `_ready` and `_return_to_new` clear both marks.
- Put a second line into the comment on the pull request: `<!-- devops roadmap implement run: <job> -->`, where `<job>` is the value of `implement.job` (the name of the runner Job, which the Service writes before it makes the Job), or `manual` when the record holds none. The first line stays `CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER`, because `retry_asked`, `retitle.py` and `stop_clear.py` match it. The Job reads the comments of the pull request once, with `list_issue_comments`, and keeps the comment that holds its run marker. Each later comment of the same Job is an update of that comment (`update_issue_comment`) with the table of all steps of the Job. A Job with no outcome, no amendment, no scoped run and no skipped step writes no comment, so no comment has the body `-`. `comment_on_pull` returns the id of the new comment, so that the Job can update it.
- Write the spend with each passed group: `_record(group=..., sha=..., spend=self._spend())`. At the start of a Job, read `implement.spend` and add it to `ItemSpend.input_tokens` and to `_spend()`. So the item budget counts the Jobs before it, and a stop or ready writes the sum. A retry that a person asks for starts from zero spend: `_start` clears `implement.spend` when `target.retry` is true, because an item that stopped on the item budget would stop again at once. A clear of the Service (a continuation, a digest clear) removes `implement.stopped` first, so the spend carries on. `_return_to_new` clears `implement.spend`.
- Give `watch_pull` a `status_callback` for `monitor_pr`. It writes one line, `The checks of pull request #<pull> still run after <seconds> s.`, with `print_muted`, at each poll after the first that finds a check that runs. The poll interval is `DEFAULT_ROADMAP_IMPLEMENT_POLL_SECONDS`, so no new loop and no new setting. The stall limit stays at 4200 s.
- Keep `ImplementRecordKey.GROUP`, `SHA` and `WIP`. The spec requires them as a record for a person (line "The job SHALL keep `implement.group`..."), and no code reads them. A new test, `tests/invariants/test_roadmap_implement_record_keys.py`, names a reader or a spec line for each member, so a key that nothing reads is found.
- Documents: the key table of `docs/ROADMAP_WORKFLOW.md` (`tests/invariants/test_roadmap_workflow_doc.py` checks that each key is named) and `docs/roadmap/implement.md`.
- Spec deltas for `roadmap-implement-job`: the requirements on the job record and on the comment are modified, and four requirements are new. The change is observable by a consumer (the job record, the comment and the log), so it carries deltas.
- The change adds record keys and no setting. No Settings model changes. The models in `config/settings.py` use `extra="ignore"`, so an old `config.yaml` is not touched. The record reader `decode_job_record` keeps only known keys, so a record from an older version loads with no new key (a test proves it).
- Request cost per Job: one GET of the comments, and the write of the comment replaces the old POST. Each phase mark is one read of the item and one write. This is 5 requests more than before, inside the budget of #3941 and #3946. The spend rides on the group mark and adds none.
- The change fits one pull request.
- Not in this change: the typed result and the hand-off of the check log (#4071), and the comment on a stop (#3997).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job keeps the phases that passed (`implement.checked_sha`, `implement.published_sha`), keeps one comment for each run, counts the spend of the earlier Jobs, and logs the wait for the checks.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/implement/implement_pull.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/github/client.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_phase_marks.py` (new), `tests/invariants/test_roadmap_implement_record_keys.py` (new), `tests/support/roadmap_implement.py`, and the tests that count the comments of the pull request

## Feasibility

Checked on 2026-11-08 at origin/main 54e5d464, after #3677 (pull request #4188) and #4187 merged.

- No merged change, open pull request or newer issue does this work. A search of `src/devops_cli/roadmap` finds no `checked_sha`, no `published_sha` and no per-run marker in a comment.
- The comment fault is confirmed in the code and by a test. `_pull_request` runs once for each Job and calls `_comment(pull, _NOTHING_YET)`. `_comment` builds the table from `self.outcomes` of this Job, so a Job with all groups ticked posts the body `-` (`lines or "-"`). The new test `test_pr_comment_marker_a_rerun_with_no_new_outcome_posts_no_empty_comment` fails on origin/main because of this. The earlier claim of the issue, that a rerun posts a second copy of the table, is wrong: the real fault is an empty comment and no marker to tell the runs apart.
- No run id exists in the code. The Service writes `implement.job` (the name of the runner Job) in `implement_submit._create`, before it makes the Job, so the runner reads it from `item.job_record`. A Job that the Service did not make has no value, and uses the fixed id `manual`.
- `client.list_issue_comments` (one paginated GET) and `client.update_issue_comment` (one PATCH) exist in `src/devops_cli/github/client.py`. `comment_on_pull` returns nothing today, and the Job needs the id of a new comment to update it, so it returns the id.
- The spend fault is confirmed. `_record` accepts `spend` but `_groups` does not pass it. `_item_spend()` sums `self.outcomes` of this Job. The new tests `test_spend_survives_kill_*` fail on origin/main: the record holds no spend after a kill, and a continuation with an item budget of 150 finishes, where the sum of 100 and 100 must stop it.
- `monitor_pr` in `src/devops_cli/github/pr_monitor.py` has the parameter `status_callback(status, elapsed)`, called at each poll. So the progress line needs no new loop.
- Old records: `decode_job_record` keeps only the keys of `ImplementRecordKey`, so the two new keys must be members, or the in-memory store and the real store drop them. A record with the old `implement.spend` JSON (requests, input_tokens, output_tokens, steps, tiers) stays valid, because the Job adds to the totals and keeps the same shape.
- The new tests on origin/main: 24 of the 52 cases of `tests/roadmap/implement/test_roadmap_implement_phase_marks.py` and `tests/invariants/test_roadmap_implement_record_keys.py` fail, each on its own assertion. The other 28 cases guard a trap (a retry starts from zero, a return clears the spend, a ready item holds no phase mark) or name a reader of an existing key. The run is cited in the pull request comment.
- A real GitHub remote and a real Service were not tested. The tests use a real git clone with a local `origin`, a scripted model and a fake of the GitHub API.

## Existing Tool Considered

The item record marks (`set_marks`), `list_issue_comments` and `update_issue_comment` of the GitHub client, and the `status_callback` of `monitor_pr` cover the need. They are existing code of the project, and no open library marks the phases of one job in an issue record. No new library is needed. The change deletes no code. Cost to build: about 90,000 tokens and 4 hours (two keys, the comment marker, the spend sum, the log line and the tests). Cost to keep: about 4,000 tokens each quarter. Cost to fix one miss: about 20,000 tokens and 1.5 hours.

## Dependencies

None. #3677 and #4187 are merged. #4071 (typed result and hand-off of the check log) waits on this change.
