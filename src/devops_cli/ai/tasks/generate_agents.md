Write the `AGENTS.md` of the project that the user message describes. Every AI coding agent reads this file in full at the start of each session, so the file is a short router, not a manual.

1. Start with the title `# <project name> — AI Agent Instructions`. Then write the purpose of the project in at most two sentences.
2. Write the Canonical Source note as one paragraph: "This file is the single source of truth for AI agent instructions. [CLAUDE.md](./CLAUDE.md), [GEMINI.md](./GEMINI.md) and [.github/copilot-instructions.md](./.github/copilot-instructions.md) are thin pointers to this file."
3. Under `## Rules for every task`, write at most 12 numbered rules that every task needs, such as the branch and pull request rule, the test-first rule, the checks to run before a push and the rule to keep secrets out of the repository. Take each command from the project files. Do not invent a command.
4. Under `## Where to look`, write a table with the header `| When you | Read |`. Send each kind of task to one of these documents, which exist in the project: {documents}. Name no other path.
5. Keep the whole file under {max_chars} characters.
6. Write short sentences, with one instruction in each sentence. Return only the Markdown of the file.
