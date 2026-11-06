# Tasks

## 1. The contributing guide gives the shell notes (other)

- [x] 1.1 Add the subsection "Shell notes for agents" at the end of section 3 of `CONTRIBUTING.md`. It says that the Bash tool of Claude Code runs zsh in the devcontainer, and it names `.devcontainer/devcontainer.json`. It gives the check `echo $ZSH_VERSION` and says which forms work in bash and in zsh. It gives three points, each with the wrong command and the right command. Point 1 is a file list in a variable. The right forms are `${=F}`, an array, or `$(cmd)` in the argument list, with a list of Python files that exist. Point 2 is a word that starts with `=` and has more text. The right form is `printf '%s\n' '-----'`. Point 3 is the two causes of broken JSON from `uv run devops gh api`. These are the stderr lines that `2>&1` mixes in, and `echo "$VAR"` in zsh. The right commands for point 3 are a direct pipe, `print -r --`, `printf '%s'` and `--jq`. The text claims nothing about control characters in a pull request body. Each sentence has at most 25 words.
  Verification: `uv run devops ci docs`
- [x] 1.2 Check that the commands of the document exist and that the change folder is valid
  Verification: `uv run devops docs check && uv run devops openspec check`
