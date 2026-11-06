# Tasks

## 1. The contributing guide gives the shell notes (other)

- [x] 1.1 Add the subsection "Shell notes for agents" at the end of section 3 of `CONTRIBUTING.md`. It states that the Bash tool runs zsh in the devcontainer and names `.devcontainer/devcontainer.json`. It gives three points, each with the wrong command and the right command: a file list in a variable (`${=F}`, an array, or `$(cmd)` in the argument list), a word that starts with `=` (`printf '%s\n' '-----'`), and the `Bytecode compiled` and `Elapsed:` lines of `uv run devops gh api` (`--jq`). Each sentence has at most 25 words
  Verification: `uv run devops ci docs`
- [x] 1.2 Check that the commands of the document exist and that the change folder is valid
  Verification: `uv run devops docs check && uv run devops openspec check`
