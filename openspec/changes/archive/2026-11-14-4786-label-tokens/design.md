# Design

## Context

A comment names the token, and a test cannot read a comment. The base file holds the category colors and the light file holds the semantic ones.

## Goals

- One test fails when a token value changes.

## Decisions

- **A mapping in code.** `LABEL_COLOR_TOKENS` holds the token name of each member.
- **Both files.** The lookup merges the base and light files, because each holds part of the set.

## Risks

- A token rename breaks the test with a KeyError. That is the change a person should see.

## Tests

- The mapping covers every member, and each value equals the token value without `#`, in uppercase.
