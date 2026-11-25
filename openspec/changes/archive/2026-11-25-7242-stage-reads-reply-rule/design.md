# Design

## Decisions

1. **One rule for each read.** `src/devops_cli/roadmap/trust.py` stays the only place that decides an author. `is_trusted`, `is_bot_filed` and `trusted_replies` take the Protocol `Authored`: a record with `author_association` and `author_login`. An `Item`, an `IssueView`, an `OpenItem`, a `CommentView` and the author of a pull request node all have this form.
2. **The title of an item of another account is left out.** Refine sends no item of another account to a model (`_outside_author` in `src/devops_cli/roadmap/refine/refine.py`), and the alternatives job selects only an item that `is_trusted` accepts (`_is_eligible` in `src/devops_cli/roadmap/alternatives.py`). Each sends only the title of its own item. So the stage job gives no title of an item of another account either.
3. **One wording.** `trust.TITLE_LEFT_OUT` is the text that stands for such a title in each place. `stage_github.ITEM_TEXT_LEFT_OUT` is the line that stands for the title, the body and the comments of one item.
4. **The filter runs before the cut.** `GitHubClient.get_last_comments` returns each comment of the pages that it reads, and `stage_github.last_trusted_comments` keeps the comments of trusted authors and then cuts to `CONST_ROADMAP_STAGE_ISSUE_COMMENTS` (3). The pages and the requests are the same as before.
5. **The issue index leaves the issue out.** The reader of `issue-index.jsonl` is a text search by a word of the title or the body. An entry with no title and no body gives that search nothing, and each line keeps the same keys.
6. **An unknown author is not trusted.** A pull request whose author `prepare` could not read gets no patch text. A pull request node with no author fields gets no title. `is_trusted` accepts no record with no relation and no login.
7. **The plan mark stays.** `_open_pull` computes `plan` from the title of each pull request, and the checks of the plan read it. Only the title text is left out.
8. **Only an author of the type `Bot` has a bot login.** GraphQL gives the login of a bot with no `[bot]` end and with the type `Bot`. `stage_overlap._author` adds the end for that type only, so a user whose login is equal to the name of a trusted bot is no bot.

## Rejected alternatives

- **Cut to the last 3 comments, then filter**: rejected. `CONST_ROADMAP_STAGE_ISSUE_COMMENTS` is 3, so three later comments of other accounts would leave no comment of a person in the answer. The test `test_read_issue_keeps_the_comment_of_a_person_when_outside_accounts_comment_after_it` holds this case.
- **Read the comments with the store (`comments_on`)**: rejected. `GitHubRoadmapStore.comments_on` in `src/devops_cli/roadmap/stores/github_store.py` reads every page of the comments, and `get_last_comments` reads the last page only. The store also gives no pull request as an `Item`, so the read of the author would still need `IssueView`.
- **An index line with the number and the labels only**: rejected. The test `test_prepare_writes_bounded_issue_index_for_3000_open_issues` reads `body` of each line, and a line with no `body` key breaks a reader that does the same.
- **A second trust function that takes a relation and a login**: rejected. The four callers would each build the two values, and `trust.py` would hold two entries to one rule. The Protocol adds 14 lines and changes no caller of `is_trusted`.
- **A read of the author of each open pull request with REST**: rejected. `open_pulls` makes one GraphQL request for each 100 pull requests (`PULL_PAGE_SIZE`), and a REST read would add one request for each pull request. The query takes `authorAssociation` and `author { __typename login }` in the same request.
