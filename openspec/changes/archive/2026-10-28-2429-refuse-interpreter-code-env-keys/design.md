# Design

## Decisions

- **The source is the `env_delete` table of sudo.** sudo removes these keys before it runs a program for another user, so the table is the maintained list of keys that change the code that a program runs. The guard takes its zsh and interpreter keys that load or run code. The manual page of each shell and interpreter, and a probe where the tool is installed, confirm each key (proposal, Feasibility).
- **The refused keys, with their sources.**

  | Family | Keys | Source |
  | :--- | :--- | :--- |
  | zsh | `ZDOTDIR`, `FPATH`, `NULLCMD`, `READNULLCMD` | `zsh(1)`, `zshparam(1)`, sudo |
  | Python | `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PYTHONUSERBASE`, `PYTHONPLATLIBDIR`, `PYTHONPYCACHEPREFIX` | `python(1)`, sudo, probe |
  | Node.js | `NODE_OPTIONS`, `NODE_PATH`, `NODE_COMPILE_CACHE`, `NODE_REPL_EXTERNAL_MODULE` | `node(1)`, sudo, probe |
  | Perl | `PERL5OPT`, `PERL5LIB`, `PERLLIB`, `PERL5DB` | `perlrun(1)`, sudo |
  | Ruby | `RUBYOPT`, `RUBYLIB` | `ruby(1)`, sudo |
  | Java | `JAVA_TOOL_OPTIONS`, `JDK_JAVA_OPTIONS`, `_JAVA_OPTIONS`, `CLASSPATH` | `java(1)`, the JVM TI specification, HotSpot `arguments.cpp`, sudo |

- **Exact names, not interpreter families.** The constant lists each key by its name. A pattern such as `PYTHON*` or `NODE_*` also refuses keys that load no code and that a caller has a reason to set, for example `PYTHONUNBUFFERED`, `PYTHONIOENCODING` and `NODE_ENV`. `DEFAULT_ALLOWED_ENV_VARS` holds `PYTHONUNBUFFERED` and `PYTHONDONTWRITEBYTECODE` for this reason. The test of the accepted overrides pins the exact names with `PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE` and `NODE_ENV`.
- **A key that runs code only in some runs is refused too.** `FPATH` loads a function only when the script marks it `autoload`. `NULLCMD` and `READNULLCMD` run only for a command line that has only a redirection. `PERL5DB` runs only with `perl -d`, `NODE_PATH` only for a module that `node_modules` does not hold, `NODE_REPL_EXTERNAL_MODULE` only for the REPL of `node`, and `PYTHONSTARTUP` only in interactive mode. #2433 refused `PS4` on the same grounds: a caller has no reason to set one of these keys, and the value is code or the place of code.
- **Four Python and Node.js keys are refused, although sudo does not list them.** `python(1)` and `node(1)` list them, and each one makes the interpreter run code from a place that the caller chooses:
  - `PYTHONPLATLIBDIR` moves the standard library directory, as `PYTHONHOME` does. The probe ran an `encodings` module from the named directory at the start of `python3 -c pass`.
  - Python reads the bytecode of a module from the directory of `PYTHONPYCACHEPREFIX`. The probe ran the bytecode of a file with the time stamp and size of the source in place of the source.
  - Node.js reads the compiled code of a module from the directory of `NODE_COMPILE_CACHE`, and it checks only the length and the CRC32 of the source. The probe ran the cached code of one file in place of a second file with the same length and CRC32.
  - The REPL of `node` loads the module of `NODE_REPL_EXTERNAL_MODULE` in place of the built-in REPL, as Python runs the file of `PYTHONSTARTUP`.
- **`JDK_JAVA_OPTIONS` is refused, although sudo does not list it.** The `java` page says that it prepends its content to the command-line options, as `JAVA_TOOL_OPTIONS` does for the JVM. Thus it can hold `-javaagent`, which loads an agent.
- **No refused key reaches an isolated child from the environment.** `DEFAULT_ALLOWED_ENV_VARS` removes `PYTHONPATH` and `PYTHONHOME`. Then no entry of the allowlist or of `DEFAULT_ALLOWED_ENV_PREFIXES` matches a refused pattern, and a test pins this with every refused key in the environment. A person who wants the ambient value in a child keeps two paths: `isolate_env=False`, and the `extra_allowed_keys` of a caller. In both, the person chose the value, as the design of #2205 says.
- **The comment of the constant keeps the length rule of #2433.** The comment above `CONST_CODE_LOADING_ENV_PATTERNS` has 25 words. It names the sudo `env_delete` list and says that the manual page of each family is above it. A short comment in the tuple names the page above the keys of each family, for example `# python(1)`. Thus each key has its source next to it, and the comment does not grow with each family.
- **The tests are in the behaviour file of the guard.** The tests check what `build_subprocess_env` does, not a committed file, so they are not invariant tests. docs/TESTING.md puts a regression test in the file of the behaviour that it pins: `tests/test_subprocess_env_boundary.py`.
- **The purpose of the spec names the interpreter.** The purpose of `subprocess-environment` names only the dynamic loader and the shell. A delta cannot change a purpose, so the change edits the purpose line of `openspec/specs/subprocess-environment/spec.md` directly.

## Rejected alternatives

- **Take every key of the sudo table.** The table also removes keys that load no code, for example `IFS`, `RES_OPTIONS`, `HOSTALIASES` and `TERMINFO`, and the full `LD_*` family, which the design of #2205 rejected. It also removes `GIT_SSH_COMMAND` and `GIT_CONFIG_*`, and devops-cli gives git the override `GIT_SSH_COMMAND` (`src/devops_cli/config/constants.py`). The git keys need a decision of their own: #2483.
- **Refuse whole interpreter families with patterns.** The reason is in Decisions: the patterns refuse keys that load no code and that a caller sets.
- **Start each interpreter child in its isolated mode, for example `python -I`.** Only some interpreters have such a mode, and the caller of `run_subprocess` does not always know which interpreter a program starts. For example, Semgrep is a Python program behind a launcher script. The guard in `build_subprocess_env` covers every child in one place.
- **Refuse the ambient keys with `isolate_env=False` or `extra_allowed_keys`.** The person chose those values, and the caller asked for them. The design of #2205 made the same decision for the loader and bash keys.

## Keys considered and accepted

- `TMPPREFIX` of zsh and `PERLIO_DEBUG` of Perl are in the sudo table. They name a file that the child writes, not code that it runs.
- `PYTHONINSPECT` is in the sudo table. It starts the interactive mode after the program, and the code comes from the standard input that the caller gives.
- `PYTHONWARNINGS` and `PYTHONBREAKPOINT` name an installed module that the child can import without them. A caller has a reason to set them, for example `PYTHONWARNINGS=ignore` or `PYTHONBREAKPOINT=0`.
- `HOME` makes a child run code from the directory that it names. zsh reads `$HOME/.zshenv` when `ZDOTDIR` is not set, and Python runs the `import` lines of the `.pth` files in the user site directory below `HOME` when `PYTHONUSERBASE` is not set. Thus `HOME` has the effect of the refused `ZDOTDIR` and `PYTHONUSERBASE`. The guard accepts it, because a caller must be able to give a child its own home directory: `src/devops_cli/telemetry/semconv.py` sets `HOME` to a temporary workspace for weaver. A caller that sets `HOME` chooses the start-up files of the child, so it must give a directory that it controls. The test of the accepted overrides pins `HOME`.

## Non-goals

- The git keys that make a git child run a program, for example `GIT_CONFIG_*`, `GIT_SSH_COMMAND` and the allowed `GIT_EXEC_PATH`, `EDITOR` and `PAGER`: #2483.
- The library keys that make a library of the child load a module, for example `OPENSSL_CONF`, `OPENSSL_MODULES` and `OPENSSL_ENGINES` of OpenSSL: #2503. `node(1)` lists `OPENSSL_CONF`, but the key has an effect in each program that uses OpenSSL, for example `curl` and the `ssl` module of Python, not only in Node.js. With isolation on, no ambient OpenSSL key reaches the child, because no allowed key or prefix matches it.
