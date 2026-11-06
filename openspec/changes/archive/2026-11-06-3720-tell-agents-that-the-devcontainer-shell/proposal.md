# Proposal

## Why

The Bash tool of Claude Code in the devcontainer runs zsh, not bash (#3720). Three behaviors cost a round trip in agent sessions. A variable that holds a file list is not split into words. A word that starts with `=` and has more text is a command lookup. JSON from `uv run devops gh api` fails to parse when `2>&1` mixes in the stderr lines. It also fails when zsh `echo` expands the backslash escapes of a variable. A subagent reads the project instructions, but it does not read the notes of the main session. So each subagent finds these mistakes again.

## What Changes

- `CONTRIBUTING.md` gets the subsection "Shell notes for agents" at the end of section 3, the inner loop.
- The subsection states the scope first. The Bash tool of Claude Code runs zsh in the devcontainer. The tool of another agent can run bash. The text gives the check `echo $ZSH_VERSION` and says which forms work in bash and in zsh.
- The subsection holds three points. Each point shows the wrong command and the right command.
- Point 1 is the file list in a variable. The right commands list only Python files that exist.
- Point 2 is the word that starts with `=` and has more text.
- Point 3 is the two causes of broken JSON from `uv run devops gh api`. The stderr lines that `2>&1` mixes in are one cause, and `echo "$VAR"` in zsh is the other.
- The change adds no rule to `AGENTS.md`. `AGENTS.md` already sends an agent to `CONTRIBUTING.md` to run one check. Each rule lives in one document only.
- The change adds no code and no setting. It does not set `SH_WORD_SPLIT`.
- The change alters no behavior that a consumer observes, because it edits one document. So it has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `CONTRIBUTING.md`.
- The documentation inventory (`CONST_DOCS_INVENTORY`) needs no change, because the change adds no Markdown file.
- No command, option or message changes, so `devops docs generate --sync-readme` has nothing to regenerate.

## Feasibility

- Scope. In the Bash tool, `SHELL` is `/bin/zsh`, `ZSH_VERSION` is `5.9.2`, and errors carry the zsh prefix `(eval):1:`. `getent passwd vscode` gives `/bin/zsh`. The `common-utils` feature in `.devcontainer/devcontainer.json` sets `installZsh` and `configureZshAsDefaultShell` to `true`. `.devcontainer/Dockerfile` sets no shell. So the text says the devcontainer, not every machine.
- Scope, other tools. `AGENTS.md` is the source of `GEMINI.md` and the Copilot pointer, and their shell tools can run bash. The text says "the Bash tool of Claude Code" and gives `echo $ZSH_VERSION`, which prints a version only in zsh.
- Bash and zsh forms. In bash, `$F` splits. In bash, `${=F}` and `${(f)F}` fail with `bad substitution`, and `print -r --` fails with `command not found`. `printf '%s'`, `$(cmd)` and `"${files[@]}"` work in bash and in zsh.
- Point 1. In the Bash tool, `F=$(printf 'a\nb\n'); printf '[%s]' $F` prints one argument that holds a newline. In `zsh -f`, these forms each print separate words: `${=F}`, the array `files=(${(f)"$(cmd)"})` with `"${files[@]}"`, and `$(cmd)` in the argument list. `ruff check $F` reports `io-error: No such file or directory`, and `ruff check ${=F}` passes.
- Point 1, file names. In a scratch repository, `${=F}` and `$(cmd)` split `c d.py` into `c` and `d.py`. The array keeps `c d.py`. Git quotes the non-ASCII name `é.py` as `"\303\251.py"`, so the array fails on it. `git diff -z` with `${(0)"$(cmd)"}` keeps all three names.
- Point 1, file list. `git diff --name-only origin/main` also lists deleted files, and `ruff check gone.py` reports `E902 No such file or directory`. `ruff check` on `.devcontainer/Dockerfile`, `uv.lock` and similar files reports `invalid-syntax`, because `ruff` lints an explicit path as Python. A Markdown file only gets a warning. So the text uses `git diff --name-only --diff-filter=d origin/main...HEAD -- '*.py'`.
- Point 2. In the Bash tool, `echo =========` prints `======== not found` and exits with status 1. A later command in the same call does not run, also when it is on the next line. `echo =` prints `=`, so the text says a word that starts with `=` and has more text. `printf '%s\n' '-----'` and `echo '========='` print the text.
- Point 3, first cause. `uv run devops gh api ... --jq .number` shows a `Bytecode compiled` line, the value and an `Elapsed:` line. With `>/dev/null` only the two lines remain. With `2>/dev/null` only the value remains. So both lines go to stderr. The `Bytecode compiled` line comes from `uv run`, because `devops gh api` alone prints only the `Elapsed:` line. In a git worktree, `uv run` also prints `warning: VIRTUAL_ENV ... will be ignored`. `json.load` of stdout reads the 100 newest pull requests. `json.load` of the output with `2>&1` fails with `Expecting value: line 1 column 1`.
- Point 3, second cause. In zsh, `echo "$VAR"` expands backslash escapes. For `P='{"body":"line one\nline two"}'`, `echo "$P"` piped to `json.load` fails with `Invalid control character`. `print -r -- "$P"`, `printf '%s' "$P"` and `echo -E "$P"` parse.
- Point 3, real reply. For `P=$(uv run devops gh api repos/dan-petty/devops-cli/pulls/<n>)`, `echo "$P"` and `2>&1` fail `python3 -m json.tool`. `print -r --`, `printf '%s'` and a direct pipe pass it.
- Difference from the issue. The issue names control characters in a pull request body. The 100 newest pull request bodies hold none, and stdout alone parses. So the text does not claim that a body holds control characters. It names the two causes above.
- Existing documents. `git grep -i zsh -- '*.md'` finds no shell note for agents. `docs/DEVCONTAINER_USAGE.md` only lists zsh as a tool of the image.

## Existing Tool Considered

The zsh manual (`zshexpn`, the option `SH_WORD_SPLIT`) explains the behavior, and the tool is zsh itself. Setting `SH_WORD_SPLIT` in the devcontainer would make zsh split words like bash. It would also change every zsh script and plugin of the user. So the change documents the behavior and does not change the shell. A document needs no build, so no written cost applies. The change deletes no internal code.
