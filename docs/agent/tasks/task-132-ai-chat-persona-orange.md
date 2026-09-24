# Task 132: Render AI Chat Persona Title in Orange Styling

**Issue**: [#132](https://github.com/dan-petty/devops-cli/issues/132)
**Status**: Done
**Milestone**: `v0.2.16`
**Priority**: `priority/p2-medium`
**Scope**: `scope/ai`

---

## 1. Description & Architectural Objectives

In `devops ai chat`, update the rendering of the AI persona title to use orange styling (`[bold dark_orange]`) in the section header rule and in prompt turns when the persona responds, while ensuring `"You:"` retains its existing color and formatting (`[bold cyan]You:[/bold cyan] `).

### Key Acceptance Criteria
1. Section header displays `[bold dark_orange]{persona_def.title}[/bold dark_orange]` with `style="dark_orange"`.
2. Persona reply prompt outputs `[bold dark_orange]{persona_def.title}:[/bold dark_orange] ` using Rich console.
3. User prompt remains `[bold cyan]You:[/bold cyan] `.
4. Comprehensive unit tests verify formatting and ANSI/markup rendering.

---

## 2. Implementation Progress

- [x] Ground issue in GitHub tracking (#132) under milestone `v0.2.16`.
- [x] Create task tracking document `docs/agent/tasks/task-132-ai-chat-persona-orange.md`.
- [x] Update `src/devops_cli/commands/ai.py` to use `[bold dark_orange]` for section header rule and persona reply prompt.
- [x] Update `tests/test_ai_cmd.py` asserting bold dark_orange persona title and bold cyan user prompt.
- [x] Verify tests, ruff, and mypy passing cleanly.
