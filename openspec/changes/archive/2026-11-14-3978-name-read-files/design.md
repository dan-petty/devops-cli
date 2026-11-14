# Design

## Context

The prompt states that every path of a task goes in a code span and that the check reads each path at the staged commit. `named_files` reads the spans and keeps only existing files. A group that names its new file only packs nothing.

## Goals

- Give the model a rule that packs at least one file for each changing group.
- Keep the rule beside the code-span rule.

## Decisions

- **One sentence after the path rule.** It names the existing-file requirement, `named_files` and the packed files.
- **No validator.** The plan check already refuses a group that packs no file; this change guides the model that writes the plan.

## Risks

- A document-only group changes no file under `src/`, but the rule reads "changes files", so it names its document. `named_files` packs an existing document too.

## Tests

- The prompt holds the sentence, and the test fails when it is removed.
