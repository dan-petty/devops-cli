# Design

## Decisions

- **Close the open block on write, in `with_record`.**: Each adapter writes the record through `with_record`: the GitHub store in `_edit_issue`, the in-memory store in `write_issue_body` and `_relabel`, and intake in the body of a new issue. One change in `with_record` therefore covers each writer. A record inside an open fence or `<pre>` shows as code on GitHub, so a reader that finds a record inside an open block does not fix the defect.
- **Use `close_open_block` of `body_hash.py`.**: #6627 added it for the job block markers, and its probe is a one-line comment after a blank line, as the record block is. A second parser could disagree with it on an edge case.
- **Import `close_open_block` inside `closed_body`.**: `body_hash.py` imports `Item` and `RefineRecordKey` from `store.py`, so an import at the top of `store.py` makes a cycle. The import invariant accepts an import inside a function (#848), and `get_roadmap_store` uses the same form for `github_store`.
- **Take one line break at the end off the body before the close.**: `close_open_block` puts its close after a line break. A body that ends in a line break then gets an empty line in its code. Without that one line break, markdown-it-py renders the body that a read gives back as it renders the body alone, which keeps the rendered form that #6729 asks for.
- **Keep the body as it is when no block is open.**: The acceptance of #6729 asks for the same text as before. On 2026-11-22, 834 of the 836 open issues held a record block, and the new `with_record` wrote each of the 836 bodies with the same text as the code of origin/main.
- **Compare the read-back of the GitHub store with the body that it wrote.**: `_edit_issue` compared the read-back body with the body before the close, so it counted the close as an edit of a person in `devops_cli_roadmap_record_lost_edit_total`. The body that `split_record` gives for the written text is `closed_body` of the body, which is the body that the write keeps. The first check compares the body of the Item with the body before the write. An earlier write from the same read can add the close, so that check also accepts `closed_body` of the body of the Item.
- **Accept one more round of a job on a body that ends in an open block.**: Refine and alternatives record the hash of the body that they read, and the close changes that text one time. The next round records the new hash, and the second write keeps the body, so no round after it sees a change. A test runs four rounds against each adapter.

## Rejected alternatives

- **Read the record from inside an open block.**: GitHub shows the record text as code, and a person who closes the block later moves the record into the middle of the body.
- **Close the open block when the store reads the body.**: The read would give a body that GitHub does not hold, so the lost-edit check of the GitHub store would see a change on each write. The read would also parse each body that holds no record, which #4445 removed.
- **Move `close_open_block` to a module that `store.py` can import at the top.**: #6736 changes `body_hash.py` at the same time. A move in this change makes the two pull requests conflict. The import inside the function has no cost after the first call.
- **Record the hash of the closed body in refine and alternatives.**: The change would touch the writers of #6736 and saves one round on a rare body. On 2026-11-22, no body of the 836 open issues ended in an open block.
