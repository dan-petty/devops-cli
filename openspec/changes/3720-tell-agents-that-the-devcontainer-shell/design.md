# Design

## Context

See proposal.md for the motivation and the scope (#3720). `CONTRIBUTING.md` section 3, the inner loop, is where an agent learns how to run one check, and `AGENTS.md` routes an agent there. The Bash tool of an agent in the devcontainer runs zsh. The shell notes of the main session do not reach a subagent, so the notes belong in the repository.

## Goals / Non-Goals

**Goals:**
- Tell an agent that the devcontainer shell is zsh, and say that another machine can run bash.
- Give three points with the wrong command and the right command each: a file list in a variable, a word that starts with `=`, and the extra lines of `uv run devops gh api`.
- Keep the text short, in ASD-STE100, with at most 25 words in a sentence.

**Non-Goals:**
- Add a rule to `AGENTS.md`.
- Change the shell, its options or a script.
- Teach zsh in general: the subsection holds only the three points that cost a round trip.

## Decisions

### 1. The subsection lives in section 3 of `CONTRIBUTING.md`

- **Decision**: Add the heading "Shell notes for agents" at the end of section 3, after item 4.
- **Alternative considered**: A rule in `AGENTS.md`.
  - *Rejected*: Each rule lives in one document, and `AGENTS.md` holds rules and routes. A note about a shell is not a rule, and `AGENTS.md` already sends an agent to `CONTRIBUTING.md` to run one check.
- **Alternative considered**: A new document for shell notes.
  - *Rejected*: Every Markdown file belongs to one class of `CONST_DOCS_INVENTORY`, and a document of three points adds a file for a reader to find. Section 3 is where the commands of the inner loop are.

### 2. The text states the scope as the devcontainer

- **Decision**: The first sentence says that the Bash tool runs zsh in the devcontainer, and the next one gives the evidence (`SHELL` and `.devcontainer/devcontainer.json`). It says that another machine can run bash, where `${=F}` and `${(f)...}` are errors.
- **Alternative considered**: Say that the agent shell is zsh without a scope.
  - *Rejected*: The evidence covers the devcontainer only. A host outside the devcontainer, or a runner, can use bash, and a wrong scope sends an agent to a form that fails there.

### 3. The text states the verified cause of the `devops gh api` lines

- **Decision**: Say that `uv run` prints `Bytecode compiled` and `devops` prints `Elapsed:`, that both go to stderr, and that `2>&1` puts them in the data. The right command is `--jq`.
- **Alternative considered**: Say that a pull request body holds control characters, as the issue does.
  - *Rejected*: No body of the 100 newest pull requests holds one, and the JSON of stdout parses. Only the merged stderr lines break `json.load`, and the text states what a command shows.

### 4. The shell stays as it is

- **Decision**: Document the behavior and keep the default options of zsh.
- **Alternative considered**: Set `SH_WORD_SPLIT` in the devcontainer so that zsh splits words like bash.
  - *Rejected*: The option changes every zsh script and plugin of the user, and the user did not ask for it. A note costs less than a change to the shell of the user.

## Risks / Trade-offs

- [The text goes stale if the devcontainer changes its default shell] → The text names the file that sets zsh, `.devcontainer/devcontainer.json`, so a reader can check the claim.
- [Another agent tool in the devcontainer runs bash] → The text says what the Bash tool of an agent runs, and a form that works in both shells is the `$(cmd)` in the argument list.
