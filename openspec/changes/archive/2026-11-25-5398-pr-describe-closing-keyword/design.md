# Design

## Decisions

- **Fix both `scaffold_proposal` and `proposal_why`**: Updating only the scaffold would leave all existing archived and active proposals failing under `devops pr describe`, whereas updating only `proposal_why` would keep new proposals nudging authors to write `Closes #N`. Changing both keeps new proposals clean and accepts legacy proposals.
- **Keep `_CLOSING_KEYWORDS` in one place (`stage_change.py`)**: Adding `strip_closing_keyword(text: str, issue: int) -> str` alongside `closing_keyword_in` avoids duplicating GitHub closing verb lists across modules.
- **Only strip closing clauses targeting the delivered issue (without another `owner/repo#N` prefix)**: A bare `Closes #5434` (with optional `and ` prefix, `:` separator, or surrounding sentence punctuation) refers to the delivered issue itself (`build_body` emits the canonical `Closes #5434` line). A closing keyword referencing another issue (`Closes #9999`) or another repository (`Closes org/other#5434`) stays intact so `closing_keyword_in` still triggers `describe_why_closes`.

## Rejected alternatives

- **Strip every closing keyword in `Why`**: Rejected because an accidental `Fixes #9999` would be silently swallowed instead of refused.
- **Edit `implement_run._why`**: Rejected because `implement_run` already falls back cleanly to the item title when `closing_keyword_in(text)` is non-None and does not block on archived proposals.
