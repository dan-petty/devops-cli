# Design

## What a route is

A route is an inline Markdown link. A path in backticks is a mention, and a reader cannot follow it. The test reads links with the parser of the test module (`_relative_links`), follows a link only to a Markdown file that exists, and counts the links from `AGENTS.md`. A chain of at most two links reaches a document, so a task gets its document from the router or from one document that the router names.

## README as the hub

`AGENTS.md` names the task kinds that need a document of their own (a test, a review, the cluster, a pull request). The references that agents look up (settings, variables, error codes, metrics, commands) go through `README.md`, which lists each one with its purpose. A new document of either class needs a link from `README.md` or from a document that `AGENTS.md` links, and the test names the document that has none.

The generated command matrix in `README.md` links each group to its page, so a page is two links from `AGENTS.md`. `docs/CLI_REFERENCE.md` is a single file for the same commands, and a page behind it would be three links away.

## Scope of the test

The test covers the classes `hand-written` and `generated` of `CONST_DOCS_INVENTORY`. Decision records, prompts, the files of the tools and the change folders are records or machine input, not routes for a task.

## Rejected alternatives

- **Raise `CONST_AGENTS_MD_MAX_CHARS`.** The cap keeps the router short enough for every agent to read in full. Only the owner changes a threshold.
- **A row in `AGENTS.md` for each kind of task.** About 350 characters for six rows against 48 spare. Merging the rows of other tasks would edit rules that the owner wrote.
- **A new `docs/README.md` index.** `README.md` already lists the references, so a second index is a second list to keep.
- **Link the pages from `docs/CLI_REFERENCE.md`.** A page is then three links from `AGENTS.md`.
- **Leave the command pages out of the test.** It is an exemption that hides 40 documents that nothing links.
- **Count a path in backticks as a route.** The first scan of the issue did, and found 2 documents instead of 52.
