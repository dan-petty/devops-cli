# Design

## Context

See proposal.md for the motivation and the scope (#3720). `CONTRIBUTING.md` section 3, the inner loop, is where an agent learns how to run one check. `AGENTS.md` routes an agent there. The Bash tool of Claude Code in the devcontainer runs zsh. The shell notes of the main session do not reach a subagent, so the notes belong in the repository.

## Goals / Non-Goals

**Goals:**
- Tell an agent that the Bash tool of Claude Code runs zsh in the devcontainer.
- Say that the tool of another agent can run bash, and give a check for the shell.
- Give three points with the wrong command and the right command each.
- The points are a file list in a variable and a word that starts with `=`.
- The third point is the two causes of broken JSON from `uv run devops gh api`.
- Keep the text short, in ASD-STE100, with at most 25 words in a sentence.

**Non-Goals:**
- Add a rule to `AGENTS.md`.
- Change the shell, its options or a script.
- Teach zsh in general. The subsection holds only the three points that cost a round trip.

## Decisions

### 1. The subsection lives in section 3 of `CONTRIBUTING.md`

- **Decision**: Add the heading "Shell notes for agents" at the end of section 3, after item 4.
- **Alternative considered**: A rule in `AGENTS.md`.
  - *Rejected*: Each rule lives in one document, and `AGENTS.md` holds rules and routes. A note about a shell is not a rule. `AGENTS.md` already sends an agent to `CONTRIBUTING.md` to run one check.
- **Alternative considered**: A new document for shell notes.
  - *Rejected*: Every Markdown file belongs to one class of `CONST_DOCS_INVENTORY`. A document of three points adds a file for a reader to find. Section 3 is where the commands of the inner loop are.

### 2. The text states the scope as the Bash tool of Claude Code in the devcontainer

- **Decision**: The first sentence says that the Bash tool of Claude Code runs zsh in the devcontainer. The next one gives the evidence (`SHELL` and `.devcontainer/devcontainer.json`). The text adds that another tool or machine can run bash, and gives the check `echo $ZSH_VERSION`.
- **Decision**: The text says which forms fail in bash: `${=F}`, `${(f)...}` and `print -r --`. It says that `printf '%s'`, `$(cmd)` and `"${files[@]}"` work in both shells.
- **Alternative considered**: Say that the agent shell is zsh without a scope.
  - *Rejected*: The evidence covers the Bash tool of Claude Code in the devcontainer only. `GEMINI.md` and the Copilot pointer also route to this document, and their shell tools can run bash. A wrong scope sends an agent to a form that fails there.

### 3. The file list holds Python files that exist

- **Decision**: The examples use `git diff --name-only --diff-filter=d origin/main...HEAD -- '*.py'`. The list leaves out deleted files and files of another type, because `ruff` reports an error for both. The text names `git diff -z` and `${(0)...}` for a non-ASCII name, because git quotes such a name.
- **Alternative considered**: `git diff --name-only origin/main`, as the issue does.
  - *Rejected*: It lists deleted files, which give `E902`, and files such as `uv.lock`, which `ruff` lints as Python.

### 4. The text states the two verified causes of broken JSON from `devops gh api`

- **Decision**: Say that `uv run` prints `Bytecode compiled` and `devops` prints `Elapsed:`, and that both go to stderr. Say that `2>&1` mixes them into the JSON. Say that `echo "$VAR"` in zsh expands backslash escapes, so a `\n` in a JSON string becomes a raw newline. The right commands are a direct pipe, `print -r --`, `printf '%s'` and `--jq`.
- **Alternative considered**: Say that a pull request body holds control characters, as the issue does.
  - *Rejected*: No body of the 100 newest pull requests holds one, and the JSON of stdout parses. Two reproduced causes break the parse: the merged stderr lines and the `echo` of zsh. The text states what a command shows.

### 5. The shell stays as it is

- **Decision**: Document the behavior and keep the default options of zsh.
- **Alternative considered**: Set `SH_WORD_SPLIT` in the devcontainer so that zsh splits words like bash.
  - *Rejected*: The option changes every zsh script and plugin of the user, and the user did not ask for it. A note costs less than a change to the shell of the user.

## Risks / Trade-offs

- [The text goes stale if the devcontainer changes its default shell] → The text names the file that sets zsh, `.devcontainer/devcontainer.json`. A reader can check the claim.
- [Another agent tool in the devcontainer runs bash] → The text gives the check `echo $ZSH_VERSION` and names the forms that work in both shells.
