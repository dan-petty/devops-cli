# Design

## Decisions

- **The context is the sentence of the tuple**: the gate checks a quoted tuple only when the sentence that holds it names `CONST_MCP_EXPOSURE_TABLE` or "exposure table" (any case; a space, a hyphen or an underscore between the two words). A sentence ends at a full stop, a question mark or an exclamation mark that a space or the end of the text follows, so a path such as `tests/conftest.py` does not end it.
- **The reason**: a quoted string tuple is a common Python literal in fixtures and parameter lists. The gate has a meaning only for a key of the exposure table, so it reads a tuple where the plan talks about that table.
- **The spec scenarios already say "the exposure table key"**: the tests now write the sentence the same way.

## Rejected alternatives

- **Require the key shape of the table (two or more lowercase words)**: a tuple such as `("a", "b")` in another table has the same shape and would still be refused. The shape cannot tell the two tables apart; the context can.
- **Check the whole Feasibility text when it names the table anywhere**: one mention of the table would again put every tuple of the plan under the gate. The sentence is the smallest unit that keeps the claim and the tuple together.
- **Delete the gate**: the gate refuses a real defect (a plan that cites a row the table lacks, as in the scenario `("ai", "ast-graph")`).
