# Proposal

## Why

The Bash tool of an agent in the devcontainer runs zsh, not bash (#3720). Three behaviors cost a round trip in agent sessions. A variable that holds a file list is not split into words. A word that starts with `=` is a command lookup. JSON from `uv run devops gh api` fails to parse when `2>&1` mixes in the stderr lines. It also fails when zsh `echo` expands the backslash escapes of a variable. A subagent reads the project instructions, but it does not read the notes of the main session, so each subagent finds these mistakes again.

## What Changes

- `CONTRIBUTING.md` gets the subsection "Shell notes for agents" at the end of section 3, the inner loop. It states the scope first: the devcontainer runs zsh, and another machine can run bash.
- The subsection holds three points. Each point shows the wrong command and the right command. The points are the file list in a variable, the word that starts with `=`, and the two causes of broken JSON from `uv run devops gh api`: the stderr lines that `2>&1` mixes in, and `echo "$VAR"` in zsh.
- The change adds no rule to `AGENTS.md`. `AGENTS.md` already sends an agent to `CONTRIBUTING.md` to run one check, and each rule lives in one document only.
- The change adds no code and no setting. It does not set `SH_WORD_SPLIT`.
- The change alters no behavior that a consumer observes: it edits one document. So it has no spec delta and sets `skip_specs: true`.
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

- Scope. In the Bash tool, `SHELL` is `/bin/zsh`, `ZSH_VERSION` is `5.9.2`, and errors carry the prefix `(eval):1:` of zsh. `getent passwd vscode` gives `/bin/zsh`. The `common-utils` feature in `.devcontainer/devcontainer.json` sets `installZsh` and `configureZshAsDefaultShell` to `true`, and `.devcontainer/Dockerfile` sets no shell. So the text says the devcontainer, not every machine. In bash, `$F` splits, and `${=F}` and `${(f)F}` fail with `bad substitution`, so the text says that another machine can run bash.
- Point 1. In the Bash tool, `F=$(printf 'a\nb\n'); printf '[%s]' $F` prints one argument that holds a newline. In `zsh -f`, `${=F}`, the array `files=(${(f)"$(cmd)"})` with `"${files[@]}"`, and `$(cmd)` in the argument list each print separate words. The array keeps a name with a space, and `${=F}` splits it. `ruff check $F` reports `io-error: No such file or directory`, and `ruff check ${=F}` passes.
- Point 2. In the Bash tool, `echo =========` prints `======== not found` and exits with status 1. A later command in the same call does not run, also when it is on the next line. `printf '%s\n' '-----'` and `echo '========='` print the text.
- Point 3. `uv run devops gh api ... --jq .number` shows a `Bytecode compiled` line, the value and an `Elapsed:` line. With `>/dev/null` only the two lines remain, and with `2>/dev/null` only the value remains, so both lines go to stderr. The line `Bytecode compiled` comes from `uv run`, because `devops gh api` alone prints only the `Elapsed:` line. `json.load` of stdout reads the 100 newest pull requests. `json.load` of the output with `2>&1` fails with `Expecting value: line 1 column 1`. This is the first cause.
- Point 3, second cause. In zsh, `echo "$VAR"` expands backslash escapes. For `P='{"body":"line one\nline two"}'`, `echo "$P" | python3 -c 'import sys, json; json.load(sys.stdin)'` fails with `Invalid control character`. `print -r -- "$P"`, `printf '%s' "$P"` and `echo -E "$P"` parse. The same holds for `P=$(uv run devops gh api repos/dan-petty/devops-cli/pulls/<n>)`: `echo "$P"` and `2>&1` fail `python3 -m json.tool`, and `print -r --`, `printf '%s'` and a direct pipe pass it.
- Difference from the issue. The issue names control characters in a pull request body. The 100 newest pull request bodies hold none, and stdout alone parses. So the text does not claim that a body holds control characters. It names the two causes above.
- Existing documents. `git grep -i zsh -- '*.md'` finds no shell note for agents. `docs/DEVCONTAINER_USAGE.md` only lists zsh as a tool of the image.

## Existing Tool Considered

The zsh manual (`zshexpn`, the option `SH_WORD_SPLIT`) explains the behavior, and the tool is zsh itself. Setting `SH_WORD_SPLIT` in the devcontainer would make zsh split words like bash. It would also change every zsh script and plugin of the user. So the change documents the behavior and does not change the shell. A document needs no build, so no written cost applies. The change deletes no internal code.
