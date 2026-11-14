# Design

## Context

`edit_pr` sends `gh pr edit` with the given fields. `_form_checked` runs on `pr create` only.

## Goals

- No edit sets a title that the `PR Title` check refuses.

## Decisions

- **The title check before the send.** `_edit_title_checked` calls `title_problems` with no declared labels: the declared-scope check needs a labels read, and the edit does not carry one. The type, the `!` rule and the length are the rules that the failures broke.
- **The create message.** The refusal holds the same bullet list as `create`.

## Risks

- An edit with a scope that the labels do not declare passes. The `PR Title` check still refuses it at merge time.

## Tests

- A `!` title and a 70-character summary are refused with the problem text, and no edit is sent.
