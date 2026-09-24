# Task 510: Text Output Functions Run Only When They Take the Text Alone

**Issue**: [#510](https://github.com/dan-petty/devops-cli/issues/510)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

`uv check` began fetching ty v0.0.84, which rejects
`schema.output_function(final_content)` in `ai/response_repair.py`. A `TextOutput` function may
take a `RunContext` and the text, or the text alone, and may be async. The call was wrong in
practice too:

- A context-taking function raised into a bare `except`, so the reply went unparsed.
- An async function returned an un-awaited coroutine as the parsed model.

### Key Deliverables Completed:

- [x] **Safe call**: `_text_only_function` returns the function only when it is synchronous and
  takes one parameter; otherwise the reply is left to the schema-free path.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_ai_fixer.py`: a text-only function parses the reply, and context-taking and
    async functions return no parsed model, with no coroutine left un-awaited
    (`-W error::RuntimeWarning`).
  - 100% passing status across Gated CI validation suite (`uv run devops ci`), including
    `uv check` with ty v0.0.84.

## 2. Note

`uv check` resolves the latest ty on each run, so a ty release can change the gate's verdict
without any change to the code. `uv check --ty-version` would pin it, which trades
reproducibility against the project's latest-tools policy.
