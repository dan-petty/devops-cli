# Proposal

## Why

Issue #2433: a person merged the pull requests of #1469, #1492 and #2205 before their review, fixes and OpenSpec archive ran. The review then found these defects on main. Each is in the scope of its issue.

- The three change folders were still active, so `openspec/specs/` did not hold their requirements.
- #2205: `build_subprocess_env` accepts a caller override of `GCONV_PATH`. #2205 asks the guard to refuse "the other glibc keys that load code", and glibc `iconv_open(3)` loads the gconv modules from the directories that `GCONV_PATH` names.
- #2205: the guard accepts the bash keys `SHELLOPTS`, `BASHOPTS` and `PS4`. bash enables the options of `SHELLOPTS` and `BASHOPTS` at start. With `xtrace` on, bash expands `PS4`, command substitution included, before each command. Thus an override of `SHELLOPTS=xtrace` and `PS4` runs code in a bash child.
- #2205: no test pins the rule that the guard refuses every key that starts with `DYLD_` or `BASH_FUNC_`. A narrower pattern passes the whole suite.
- #2205: the bullet of `ARCHITECTURE.md` says that a child gets the environment without credentials. That is true only with `isolate_env=True`. It ends its list with "and more", and a sentence has 35 words. The comment of `CONST_CODE_LOADING_ENV_PATTERNS` is one sentence of about 60 words.
- #1469: two clauses of the `config-commands` spec have no test assertion: the success line of a compliant audit, and an alert that names the leak.
- #1492: the gh pin tests are in the flat file `tests/test_service_image_gh.py`, a parallel file to the digest invariant of the same Dockerfile. The pin test sees a gh URL only as a bare token, so a URL in quotes escapes it.

## What Changes

- Archive the changes `1469-audit-keys-leak-exit-code`, `1492-drop-gh-go-trivy-ignores` and `2205-refuse-code-loading-env-keys`, one commit each.
- `CONST_CODE_LOADING_ENV_PATTERNS` in `src/devops_cli/config/constants.py` adds `GCONV_PATH`, `SHELLOPTS`, `BASHOPTS` and `PS4`. Its comment names the source of each entry in short sentences. A caller override of one of these keys raises the same `SecurityError` as the other refused keys. The refusal is a message that a consumer sees, so the change modifies the requirement of the `subprocess-environment` spec.
- `tests/test_subprocess_env_boundary.py` refuses the new keys, and it pins the prefix rule with `DYLD_` and `BASH_FUNC_` keys that no fixed list names, and with two function names.
- The child environment bullet of `ARCHITECTURE.md` describes `isolate_env` on and off, names the constant as the full list, and puts the null byte in its own sentence.
- `tests/test_config_audit_keys.py` asserts the success line of a compliant table, and the name of the leak in the security alert.
- The invariants of the Service image move into `tests/invariants/test_service_image.py`: the two gh tests, and the digest test from `tests/test_architectural_invariants.py`. The gh pin test finds each gh release URL in the Dockerfile text, also in quotes or after another character. `docs/TESTING.md` lists the new subject file.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the refused caller overrides add `GCONV_PATH`, `SHELLOPTS`, `BASHOPTS` and `PS4`.

## Impact

- Code: `src/devops_cli/config/constants.py`.
- Tests: `tests/test_subprocess_env_boundary.py`, `tests/test_config_audit_keys.py`, `tests/invariants/test_service_image.py`, `tests/test_architectural_invariants.py`, and the deleted `tests/test_service_image_gh.py`.
- Documents: `ARCHITECTURE.md`, `docs/TESTING.md`.
- Specs: `openspec/specs/config-commands/spec.md` and `openspec/specs/subprocess-environment/spec.md` from the three archives.

## Feasibility

- The three change folders were active on `origin/main` at `19412fa9`, and `uv run devops openspec archive` archived each with "Every spec and change validates".
- On `origin/main` at `d739a472`, `build_subprocess_env(env={key: "x"})` returned the key with no `SecurityError` for `GCONV_PATH`, `SHELLOPTS`, `BASHOPTS`, `PS4` and `ZDOTDIR`.
- bash 5.3.15: `subprocess.run(["bash", "-c", "true"], env=build_subprocess_env(env={"SHELLOPTS": "xtrace", "PS4": "$(echo PS4-CODE-RAN >&2)+ "}))` printed `PS4-CODE-RAN` before `+ true`. `BASHOPTS=xpg_echo` made `shopt xpg_echo` report `on`. The `bash(1)` page of that system says that bash enables each option of `SHELLOPTS` and `BASHOPTS` "before reading any startup files", and that it expands `PS4` "as with PS1" before each traced command.
- glibc 2.43 (Debian 2.43-7): a directory held a `gconv-modules` file and an `x.so` with a constructor that prints `GCONV-CODE-RAN`. `iconv -f PWN -t UTF-8`, with the environment that `build_subprocess_env(env={"GCONV_PATH": <dir>})` returned, printed `GCONV-CODE-RAN`. The `iconv(1)` page says that `iconv_open(3)` searches the directories in `GCONV_PATH` for the configuration and loads the gconv modules.
- glibc also lists `GETCONF_DIR` among the keys that it removes in secure-execution mode. `GETCONF_DIR=<dir> getconf -v POSIX_V7_ILP32_OFF32 PATH` ran no program from `<dir>` on this system, so the change does not add it.
- zsh 5.9.2 ran `$ZDOTDIR/.zshenv` for `zsh -c true`. Python 3.14.10, node v24.22.1 and perl v5.42.3 ran code from `PYTHONPATH`, `NODE_OPTIONS` and `PERL5OPT`. These keys are outside the loader, glibc and bash families of #2205, so #2429 tracks them.
- A mutant of `CONST_CODE_LOADING_ENV_PATTERNS` with only the five named `DYLD_` keys and `BASH_FUNC_*%%` passed every test of `tests/test_subprocess_env_boundary.py` on `origin/main` (review of PR #2405).
- `tests/test_service_image_gh.py` on `origin/main` keeps only the whitespace-split tokens that start with `https://github.com/cli/cli/releases/download/`. A Dockerfile copy with a quoted `curl` of v2.102.0 passed it (review of PR #2402).

## Existing Tool Considered

- The guard keeps `fnmatch.fnmatchcase` of the standard library, as #2205 decided. No maintained library publishes the set of environment keys that load code. The new entries come from the `bash(1)` and `iconv(1)` manual pages.
- The gh pin test uses `re` of the standard library over the Dockerfile text. `tree-sitter-dockerfile`, which the project already has, gives the instructions of a Dockerfile, but the shell text of a `RUN` instruction stays one string. A text search finds a URL in an `ADD`, in a `RUN` and in quotes with one rule.
- The change deletes `tests/test_service_image_gh.py`, the whitespace-token match of the pin test, and the digest test with its two helpers in `tests/test_architectural_invariants.py`. The digest test moves without a change.
