# Design

## Decisions

- **One paragraph of six sentences.** The style file allows at most six sentences in a paragraph, 20 words in a procedure sentence and 25 in a description. The new paragraph has six sentences, and no procedure sentence has more than 20 words.
- **A gate is a defined term.** The issue gives two lists: the items that go in the first line (a hold, a blocker, a person step, a merge order) and the items that stop a status word (a review, a person step, a merge order, a deployment step). One sentence defines a gate as the union of the two lists. The first sentence then puts each gate in the first line, and the third sentence refuses "done", "green" or "ready" while a gate applies. Two separate lists did not fit the limit of 20 words.
- **The test reads the request that the code builds.** The new test calls `with_style_request` and asserts each sentence of the rule. The test fails on the base, because the base text holds none of them. The existing snapshot holds the full request, so a change of any other sentence still shows in review.

## Rejected alternatives

- **A new rule in `AGENTS.md`.** `AGENTS.md` is at its limit of `CONST_AGENTS_MD_MAX_CHARS`, and rule 9 already links to `style_ste100.md`. A second copy of the rule also breaks "Each rule lives in one document only".
- **Two paragraphs, or a bullet list.** The issue asks for a change of the one paragraph. Six sentences hold the four parts of the rule and the two sentences that stay, so a split is not necessary.
- **A positive form only, "put each gate before a word such as done".** The issue asks for the rule "Do not open with done, green or ready when a gate still applies". The negative sentence keeps that rule as written.
