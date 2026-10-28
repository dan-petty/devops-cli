# Proposal

## Why

Issue #2429: the subprocess environment guard accepts the zsh and interpreter keys that make a child load or run code that its caller did not choose.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches: the loader keys of glibc and macOS, `GCONV_PATH`, and the bash keys (#2205, #2433).
- It accepts `ZDOTDIR`. zsh reads `$ZDOTDIR/.zshenv` at each start, also for `zsh -c`.
- It accepts the interpreter keys, for example `PYTHONPATH`, `NODE_OPTIONS`, `PERL5OPT` with `PERL5LIB`, and `RUBYOPT`. Each one makes the interpreter load a file or a module before the requested program.
- `DEFAULT_ALLOWED_ENV_VARS` lets the ambient `PYTHONPATH` and `PYTHONHOME` reach an isolated child. Thus a Python child, for example Semgrep or mypy, imports a `sitecustomize` module from the directory of the person.

## What Changes

- `CONST_CODE_LOADING_ENV_PATTERNS` in `src/devops_cli/config/constants.py` adds the zsh and interpreter keys that make a child load or run code. The keys come from the default `env_delete` table of sudo and from the manual page of each shell and interpreter. The design lists each key and its source.
- A caller override of one of these keys raises the same `SecurityError` as the other refused keys, with isolation on and off.
- `DEFAULT_ALLOWED_ENV_VARS` in `src/devops_cli/core/process.py` removes `PYTHONPATH` and `PYTHONHOME`. Thus no key that the guard refuses reaches an isolated child from the environment of the person.
- The child environment bullet of `ARCHITECTURE.md` names the refused families. It names the git keys as the keys that still reach a child (#2483).
- The refusal and the isolated environment are what a consumer sees, so the change modifies the requirements of the `subprocess-environment` spec and adds one requirement.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the refused caller overrides add the zsh, Python, Node.js, Perl, Ruby and Java keys that load or run code. An isolated child gets no refused key from the environment of the person.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`.
- Tests: `tests/test_subprocess_env_boundary.py`.
- Documents: `ARCHITECTURE.md`, and the purpose of `openspec/specs/subprocess-environment/spec.md`.

## Feasibility

- The guard accepts the keys today. On `origin/main` at `960e3573`, `build_subprocess_env(env={key: "x"})` returned each of `ZDOTDIR`, `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PYTHONUSERBASE`, `NODE_OPTIONS`, `PERL5OPT`, `PERL5LIB`, `PERLLIB`, `PERL5DB`, `RUBYOPT` and `RUBYLIB` with no `SecurityError`. `DEFAULT_ALLOWED_ENV_VARS` holds `PYTHONPATH` and `PYTHONHOME`.
- Each probe below ran with `env -i PATH=/usr/bin:/bin` and a key that names a temporary directory. Each printed its marker, so the child ran code from that directory:
  - zsh 5.9.2: `ZDOTDIR` with `zsh -c true` ran `.zshenv`. `FPATH` with `autoload example_fn; example_fn` ran the function file. `NULLCMD` with `> file` and `READNULLCMD` with `< /dev/null` ran the named program.
  - Python 3.14.9: `PYTHONPATH` with `python3 -c pass` imported `sitecustomize`. `PYTHONHOME` that points at a copy of the standard library imported its `sitecustomize`. `PYTHONUSERBASE` ran an `import` line of a `.pth` file. `PYTHONSTARTUP` with `python3 -i` ran the file. `PYTHONPYCACHEPREFIX` loaded a bytecode file with the time stamp and size of the source `m.py`, and `import m` ran the bytecode, not the source.
  - Node.js v24.22.1: `NODE_OPTIONS` with `--require <file>` and with `--import <file>` ran the file before `node -e 0`. `NODE_PATH` loaded a module from the directory for `require("example-missing")`.
  - Perl v5.42.3: `PERL5OPT=-MX` with `PERL5LIB` loaded `X.pm`. `PERL5LIB` and `PERLLIB` each loaded a `strict.pm` in place of the installed one. `PERL5DB` with `perl -d` ran its code.
- Ruby and Java are not installed here. The `ruby(1)` page in the Ruby source (`man/ruby.1`) says that `RUBYOPT` can hold `-r`, which loads a library, and that Ruby searches the `RUBYLIB` directories before the standard load path. The `java` page of JDK 21 says that `JDK_JAVA_OPTIONS` prepends its content to the command-line options, and that `-javaagent` loads an agent. The sudo table lists `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS` and `CLASSPATH` as Java options and the class search path.
- The default `env_delete` table of sudo (`initial_badenv_table` in `plugins/sudoers/env.c`, branch `main`) lists `ZDOTDIR`, `FPATH`, `NULLCMD`, `READNULLCMD`, `TMPPREFIX`, `PYTHONHOME`, `PYTHONPATH`, `PYTHONINSPECT`, `PYTHONUSERBASE`, `PYTHONSTARTUP`, `RUBYLIB`, `RUBYOPT`, `NODE_OPTIONS`, `NODE_PATH`, `PERLIO_DEBUG`, `PERLLIB`, `PERL5LIB`, `PERL5OPT`, `PERL5DB`, `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS` and `CLASSPATH`.
- No file in `src/`, `.github/`, `.devcontainer/` or a Dockerfile sets `PYTHONPATH` or `PYTHONHOME` for a child. The two tests that set `PYTHONPATH` (`tests/test_cli_startup_imports.py` and `tests/test_ci.py`) start their process with `subprocess` directly, not through `build_subprocess_env`. No caller in `src/` gives one of the new keys as an override.

## Existing Tool Considered

The default `env_delete` table of sudo is the maintained, open list of environment keys that change the code that a program runs. The change takes its zsh and interpreter keys that load or run code. No library publishes the table for import, so the constant copies the keys and names the sources. The match uses `fnmatch.fnmatchcase` of the standard library, as before. The change adds no code path and deletes `PYTHONPATH` and `PYTHONHOME` from the ambient allowlist.
