# Proposal: #4471

## Why

Tool results are 75% of the tokens that Claude Code carries, and no project file asks an agent for small tool output (#4471). The context audit of 2026-11-11 measured 8,679M input tokens a week for Claude Code. Answers of Loki queries alone carry 69.3M.

Agents also read AGENTS.md again about 167 times a week. Claude Code and Gemini CLI expand the import line of their pointer stub (`@AGENTS.md`, `@./AGENTS.md`), so AGENTS.md is already in their context. But the stub tells them "Read that file." after the import line.

## What Changes

- AGENTS.md gets rule 14, "Keep tool output small" (70 tokens): search before you read, read only the lines that you need, ask each command for less output (`git diff --stat`, `--jq`, `--limit`, a Loki `limit`), and keep each fact that the reader needs (error lines, `file:line`, failed test IDs). The rule adds no new number to the other rules, so each reference to a rule by its number stays correct.
- AGENTS.md has a cap of 6,500 characters (`CONST_AGENTS_MD_MAX_CHARS`). To make room, the change removes command details that the document that owns them already holds: the full `devops roadmap return` command of rule 2 (docs/ROADMAP_WORKFLOW.md), the "run `uv run devops ci` before a push if you wish" clause of rule 5 (CONTRIBUTING.md), the arguments of `devops pr threads reply` in rule 6 (`--help` and docs/SDLC.md), the intake command of rule 11 (the "file an issue" row of AGENTS.md and docs/ROADMAP_WORKFLOW.md) and the `.devops/review.toml` note of the review row (docs/SELF_IMPROVEMENT.md). The cap does not change.
- The pointer stub template has two branches. A stub with an import line says that the line loads AGENTS.md into the context of the tool, and that the tool does not read it again. A stub without an import line (GitHub Copilot) still says "Read that file." `devops ai agents` writes the stubs, so this is a change to the output of a command, and the change carries a spec delta.
- CLAUDE.md, GEMINI.md and .github/copilot-instructions.md are written again with `devops ai agents --template`.
- The knowledge base page of the scaffolding states the two branches.

## Capabilities

- `agent-instructions` (ADDED requirements): the rule for small tool output, and the text of a pointer stub with and without an import line.

## Impact

- AGENTS.md keeps its size (1,686 tokens before, 1,685 after, `count_tokens`). CLAUDE.md grows from 115 to 136 tokens and GEMINI.md from 117 to 139, so each Claude Code request carries 20 more tokens, about 1.1M a week for about 54,700 requests.
- The audit estimates a saving of about 96M raw tokens a week for the rule at 30% compliance, and about 21.7M raw tokens a week for the stub.
- The change fits one pull request.

## Feasibility

- Claude Code expands `@path` imports of CLAUDE.md into its context (Claude Code memory documentation, "CLAUDE.md imports"). This session shows it: the context of a subagent holds "Contents of /workspaces/devops-cli/AGENTS.md" next to CLAUDE.md. Gemini CLI expands `@file.md` imports of GEMINI.md (Gemini CLI documentation, "Memory Import Processor").
- `start/agents_reread.py` of the audit counted 136 Read calls of AGENTS.md in the sampled sessions after the import, 12.6M carried tokens. `start/session_mix.py` counted 1,510M of 2,192M carried tokens as tool results.
- `len(AGENTS.md)` is 6,495 characters on `origin/main` and 6,496 after the change, under the cap of 6,500 (`tests/invariants/test_agents_md.py::test_agents_md_stays_within_character_budget`).
- `git grep` finds no text in the repository that counts the rules of AGENTS.md ("rules 1 to 13"). Briefs of workflow scripts outside the repository that say so need "rules 1 to 14".

## Existing Tool Considered

No tool is necessary. The import line of Claude Code and Gemini CLI already loads AGENTS.md; this change corrects the text around it and adds one rule. The change deletes the "Read that file." sentence from the stubs with an import line, and the command details of AGENTS.md that other documents already hold.
