# Design

## Context

`select_candidates` in `src/devops_cli/roadmap/refine.py` takes the items of a round from the issue listings that the store reads (`items`, `backlog`). Each `Item` comes from `item_of`, which read the issue's fields but left out `author_association`. `sanitize_text` cleans the model's text before refine writes it into the body section and into the next-step comment. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- A round refines only an item that the owner, a member or a collaborator opened. A person can refine any other item with `--item`.
- The model's text cannot open a hidden HTML block, forge a marker or a record block, make a `www.` link, or put a backlink on an issue of another repository.

**Non-Goals:**

- Comments from outside accounts on a trusted item. Refine sends the replies to the model as data, and the item still needs a person's Priority from intake.
- Other GitHub references, such as `owner/repo@sha` or a full issue URL in an allowed markdown link.
- A change to the reply schema or to the prompts.

## Decisions

- **The association goes on `Item`.** The listing that a round reads already gives it, so the check costs no request, and the GitHub store and the in-memory store give it the same way.
  - Rejected: read `store.issues()` in refine and match the numbers. It is a second listing for each round in the GitHub store.
- **The trusted associations are intake's `CONST_ROADMAP_TRUSTED_AUTHORS` (OWNER, MEMBER, COLLABORATOR).** One list decides trust for both jobs. CONTRIBUTOR is not in it: an account becomes a contributor when one of its commits is merged, which gives it no write access.
- **An item with no association waits on a person.** GitHub gives an association for every issue, so a missing one is a defect, and the check fails closed.
- **The item waits on `NextStep.PERSON` with one detail line.** The report already groups items that wait on a person, and the detail names the association and `--item <number>`. Refine writes no comment and no record for it, so an outside account gets no reply from the bot.
  - Rejected: a new `NextStep` value. It adds a report heading and a record value for a wait that only a person ends, which `PERSON` already means.
- **The `<` of `<!` and `<?` becomes `&lt;`.** CommonMark starts an HTML block at `<!--`, `<?`, `<!` and a letter, and `<![CDATA[`, and each block hides the text up to its end mark. The entity shows `<` as text in GitHub, and the record block pattern and the markers do not match it. The step runs after tags are removed, so `<<b></b>!--` cannot make `<!--` again.
  - Rejected: a code span around `<!--`. Text with an odd number of backticks closes the span early, and the opener is then raw HTML again.
  - Rejected: a backslash before `<`. The record block pattern still matches the text after the backslash.
- **A `www.` link and an `owner/repo#N` reference go in a code span.** This is the escape that `sanitize_text` uses for handles and URLs, and GitHub does not link or cross-reference text in a code span. The `www.` pattern follows the GFM rule for the character before the link, so a `www.` inside a URL or a code span is not wrapped two times. A `www.` link that `allowed_urls` holds stays a link, as a bare URL does.
- **The `checked-at` comment goes around the sanitized text.** It is refine's own text, and the sanitizer would otherwise neutralize it, as it already did not neutralize the markers (#1470).
- **The in-memory store opens an issue for the owner by default.** GitHub always gives an association, so `None` was a state that the real store never gives. A test of an outside account gives the association.

## Risks / Trade-offs

- [An issue that the App or a bot opens waits on a person in a round] → a person refines it with `--item`. The Service files no issue; the agents file issues with the owner's credentials, which GitHub gives as OWNER.
- [A `<!` or `<?` inside a code span in the model's text shows as `&lt;`] → this changes how the text looks, not what it means. The alternative leaves an HTML block that hides the end of the body.
