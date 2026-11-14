# Design

## Context

#4630 deleted the orphan prompts and the fallbacks, but the digest still reads `ai/personas/`.

## Goals

- The digest moves only with a prompt that a review loads.

## Decisions

- **One directory.** The digest hashes `ai/tasks/` only, and `personas_dir` leaves the signature.
- **The chat personas stay out.** A chat persona is no review prompt.

## Risks

- A future review prompt under `ai/personas/` would not move the digest. That folder is the chat persona folder, and a review prompt belongs under `ai/tasks/`.

## Tests

- A persona edit holds the digest.
- An edit of `review_group_analysis.md` moves it.
- The signature holds no `personas_dir`.
