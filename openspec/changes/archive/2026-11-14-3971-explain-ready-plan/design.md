# Design

## Context

`_pull_reason` reads the pull request of an item and returns the reason that the implement job leaves the item out. Every pull request that is not an open draft gives the same message.

## Goals

- Tell a ready plan from a broken draft.
- Keep the old message for the fault cases.

## Decisions

- **The record, then the title.** A pull request is a plan when `stage.pr` equals its number, or when its title starts with `docs(openspec): plan #`. The refinement names both.
- **Only an open pull request.** A closed or merged pull request keeps the old message, because it no longer waits for a merge of its plan.

## Risks

- A person's open pull request whose title starts with the plan prefix takes the new message. The prefix is the stage job's own, and a person's plan uses the same form.

## Tests

- An open plan pull request that is no longer a draft gives the merge-wait message.
- A closed plan pull request gives the old message.
