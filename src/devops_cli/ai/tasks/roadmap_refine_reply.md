Decide each design question with the best practice, and do not leave it to a person. Find the options, and choose one with the evidence in this order: a decision that the project records (an ADR under `docs/adr/`, `AGENTS.md`, `CONTEXT.md`, or the body's "Owner decisions"); an open, maintained tool or library that covers the need, before code that the project builds and keeps itself; then the documentation or the standard of the tool, library or protocol. Cite that evidence as the decision's `sources`.

The reply has these keys and no other, at the top level or inside any criterion, question or option:

- `problem_statement`: the problem the issue solves, in a few sentences of plain text. It is required.
- `acceptance_criteria`: a list of objects, each with exactly two keys, `description` and `verification`, both plain text. `description` is one outcome a reviewer can check, and `verification` is the test, command or observation that shows it. A criterion is never a plain string.
- `key_questions`: a list of objects, each with the keys `question`, `answer`, `kind`, `sources`, `options` and `body_question`.
  - `kind` is `fact` for an answer that the repository or a document establishes; `decision` for a design choice; or `person` only for a decision that the project leaves to a person: a merge, a review verdict, a milestone, a secret, a repository setting or a host. Give your recommendation as the `answer` of a `person` question.
  - `sources` is a list of strings that name where the answer comes from, each a repository path such as `src/app.py` or `src/app.py:12`, or a URL that a web search returned. A `fact` needs at least one source. Never make up a source: refine checks each path and URL.
  - `options` is, for a `decision`, each option that you compared, as an object with exactly three keys: `option`, a short name; `chosen`, `true` for the option that the answer takes, else `false`; and `reason`, why you chose or rejected it. It is an empty list for a `fact` or a `person` question.
  - `body_question` is the `number` of the body question that the answer answers, or `null`.
- `fits_one_pr`: `true` when one pull request can deliver the whole change, else `false`.
- `split_offs`: when `fits_one_pr` is `false`, one line for each item the change splits into; otherwise an empty list.
- `suspected_block`: one line that names what outside this roadmap the work waits on, such as an upstream release or a date, or `null`. A design choice is never a suspected block: give it as a `decision`.
- `dependencies`: the numbers of the issues this one needs done first, or an empty list.
- `block_paths`: when `suspected_block` or `dependencies` is set and code in this repository causes the block, the paths of the files that hold that code, each a repository path such as `src/app.py`; otherwise an empty list. A change to one of these files makes refine look at the issue again.
