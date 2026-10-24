# Design

## Context

See `proposal.md` for motivation.
`ReviewProfile` records metadata about review runs.
When source files or prompt files change during a review run, later stages execute different code or prompts.
The profiler must record the initial prompt digest and detect changes during the run.
The corpus scoring command must refuse runs that changed while executing.

## Goals / Non-Goals

**Goals:**

- Compute the prompt digest when `ReviewProfiler` initializes.
- Record the start prompt digest in `ReviewProfile`.
- Set `code_changed_during_run: true` if source checkout or prompt files change before `build()`.
- Refuse sessions with `code_changed_during_run: true` in `score_corpus_runs`.

**Non-Goals:**

- Do not introduce a new profile field for prompt changes.
- Do not modify prompt loading logic or prompt hash algorithms.

## Decisions

- **Reuse the `code_changed_during_run` field.** Prompt files are inputs to review runs. Setting `code_changed_during_run: true` for changed prompts matches source checkout changes.
  - *Rejected Alternative:* Add a separate `prompts_changed_during_run` field. Evidence: Consumers and warnings already handle `code_changed_during_run` to signify input drift.
- **Reject changed runs in `score_corpus_runs`.** A benchmark arm compares identical runs. A run with changing inputs cannot represent an arm.
  - *Rejected Alternative:* Allow changed runs with a warning during corpus scoring. Evidence: Benchmark statistics would become invalid and misleading.

## Risks / Trade-offs

- [Corpus scoring fails for reviews that experienced modifications] → This is desired behavior. Users must run benchmarks from stable checkouts.
