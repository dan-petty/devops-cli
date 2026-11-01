# Design

## Decisions

- **The kind is a field of the group, named `kind`, with the values `behavior` and `other`.** The owner rule follows behavior, not the path. A deletion in `src/` that keeps behavior is `other`, and a new function in `src/` is `behavior`.
- **One `model_validator` on `StageGroup` states every rule of the kinds.** A reply that breaks a rule fails the schema, and `chat_structured` returns it to the model once with the problem text. The validator lists all problems of a group in one message, so one return can fix them all.
- **`behavior` needs a path under `src/` in `changes`.** A test of code needs code. The rule stops the model from calling a document change `behavior` to get a test.
- **An `other` group has exactly one of `verify` and `process`.** `verify` is one command that gives the same answer on each run. `process` is for a check with no command. A group with both has two sources of truth, and a group with neither has no proof.
- **`documentation` is `null` when the group changes no document.** `group_text` then renders no documentation task. This removes the text "Change no document, run the generator", which contradicts itself.
- **The task `n.1` of an `other` group holds the work and its verification.** It has the shape of task `n.2` of a `behavior` group, so each kind has one task per step of the work.
- **A test compares the prompts with the validator.** It reads the `GroupKind` values and the field names of `StageGroup` and checks that the stage prompt and the split prompt name them. It also checks that the implement prompt names the kind.

## Rejected alternatives

- **Decide the kind from the paths alone (no `src/` path means no test).** This is the plan in the issue body. The owner replaced it: a deletion in `src/` that keeps behavior needs no test, and a new function in `src/` needs one.
- **Keep `test` required and allow the text "none".** The model would write a placeholder, and the implement job would still try to build a test. The evidence is the plan of #2175.
- **Let the implement job decide to skip step 1.** The job would guess from the text of a task. A field in the reply is checked by code before the pull request opens.
- **Write a parser that reads the paths of `changes` to guess the kind.** The `src/` rule needs a prefix check, not a parser, and the model states the kind.
