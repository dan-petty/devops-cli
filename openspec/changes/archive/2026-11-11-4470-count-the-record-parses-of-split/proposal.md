# Proposal: #4470

## Why

#4445 made `split_record` in `src/devops_cli/roadmap/stores/store.py` faster in two ways: a body that does not hold the opening text of the record block returns `(body, {})` with no parse, and the parser of the store turns off the core rule `inline` of markdown-it. The pull request of #4445 added no test, so no test fails when a later change removes the early return or turns the `inline` rule on again. Three acceptance criteria of #4445 have no test: a body without the opening text gives no parse, a batch of 100 bodies of which 10 hold it gives 10 parses, and the parse builds no inline tokens. Closes #4470.

## What Changes

- A new test module, `tests/roadmap/stores/test_roadmap_store_record_parse.py`, holds the three criteria.
- A profile function (`sys.setprofile`) counts the calls of `MarkdownIt.parse` that `split_record` makes, and keeps the tokens of each call. It replaces no object.
- The change fits one pull request. It changes no product code.

## Capabilities

None. The change adds tests only and alters no behavior that a consumer observes, so it has no spec delta.

## Impact

- Three tests in `tests/roadmap/stores/`. Together they run in less than 1 s.
- No change to `src/`, to a document or to a dependency.

## Feasibility

- The tests fail on 6cf78e73, the base of the pull request of #4445. `devops ci fail-to-pass --base 6cf78e73`, run from a scratch worktree at 6cf78e73 with the new test module as its one commit, gives "3 failed on base": 1 parse in place of 0, 100 parses in place of 10, and an `inline` token with a `text` child. 7c595656, the parent of the merge commit, holds the same `store.py` as 6cf78e73. All three tests pass on the branch.
- markdown-it-py 4.2.0 (`uv.lock`) parses `Plain text.` with the rule `inline` off into `paragraph_open` (`children` None), `inline` (`children` `[]`) and `paragraph_close` (`children` None). With the rule on, the `inline` token has a `text` child. So the token shape that tells the two parsers apart is the empty `children` of the `inline` token. The scenario of #4445 that names a first token `paragraph` with `children` None cannot tell them apart. The archived change of #4445 holds no spec delta and does not repeat that scenario, so no archived file needs a correction.
- #4470 proposes to replace `store._BODY_MARKDOWN` with a counting wrapper. `docs/TESTING.md` (Doubles) says that no test patches a devops-cli module, class, function or attribute, and that a test reaches private code through the public interface. The profile function counts the same calls through the public `split_record` and patches nothing, so the criteria have tests with no exception to that rule.

## Existing Tool Considered

pytest and the standard library cover the need: `sys.setprofile` sees each call of `MarkdownIt.parse` and its return value. pytest-mock `mocker.spy` was considered; it replaces the attribute that it spies on, which `docs/TESTING.md` does not allow for an object that is not an edge. The change adds no library and deletes no internal code. Cost: about 15,000 tokens to build, about 500 tokens a year to keep, and about 45 minutes of elapsed time.
