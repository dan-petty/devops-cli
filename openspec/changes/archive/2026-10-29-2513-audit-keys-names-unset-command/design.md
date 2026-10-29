# Design

## Context

See proposal.md for the background. The audit scans `config_layer_paths()` and also `config.yaml` and `.devops/config.yaml` in the current directory. `devops config unset <key>` edits `get_active_config_path()`. This is the file that `DEVOPS_CLI_CONFIG` names, else the project file, else the global file. A leak names its file as `<path>:<section>.<key>` (#2426).

## Goals / Non-Goals

**Goals:**
- Make the alert name the commands that move a secret to the keyring and remove it from the file of the leak.
- Make the stored value complete for a multi-line credential.
- Name the same commands in the help and in the generated documents.

**Non-Goals:**
- The copy of the file, which `unset` makes before it writes, still holds the plaintext value. The alert says so. The fix of the copy is #2645.
- A key that a YAML merge key gives makes `unset` end with a `TypeError`. The fix is #2656.
- The audit does not scan a secret under a nested key (#2511).

## Decisions

### 1. The alert names the existing command with `DEVOPS_CLI_CONFIG`
- Decision: The alert names `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`. No option and no code path is added.
- Rationale: The command works for a key that the file holds as a key of its own, in every file that the audit scans. The error of an unknown key (#2201) already names it. One way to edit another file is simpler to keep than two.
- Limit: A key that a YAML merge key gives fails with a `TypeError` (#2656). The audit reports such a key, and the command cannot remove it.
- Alternative considered: Add `--file` to `devops config unset`, as the plan of the issue proposes.
  - Rejected: `--file` and `DEVOPS_CLI_CONFIG` then do the same work. The error of an unknown key would have to name one of them.
- Alternative considered: Make `unset` remove the key from every file of `config_layer_paths()`.
  - Rejected: It does not reach `config.yaml` in the current directory, which the audit scans but `config_layer_paths()` does not name. It also removes a value that the person may want in one of the files.
- Alternative considered: Make `devops config set` of a credential remove the plaintext value from each file that holds it.
  - Rejected: `set` writes no config file by design. The change would hide a file edit behind a store.

### 2. The alert holds a template, and it says to quote the values
- Decision: The alert says that each entry reads `<file>:<key>`. It names the commands with `<file>` and `<key>`, and it says to quote both for the shell.
- Rationale: A leak is a string `<path>:<section>.<key>`. A section name can hold shell syntax, such as `x;touch PWNED;#`. The unquoted command would run it. A command for each leak needs a parse of the string, and a key name can hold a colon.
- Alternative considered: Print one quoted command for each leak with `shlex.quote`, as the error of an unknown key does.
  - Rejected: It needs a structured leak. That changes the scan code and the JSON report, and #2511 changes the scan.

### 3. The first step names the hidden prompt and `--from-file`
- Decision: Step 1 is `devops config set <key>`, with `--from-file <path>` for a multi-line credential. The alert has no `<val>`.
- Rationale: A value in the argument list stays in the shell history and in the process list. The prompt reads one line, so it kept only the first line of a PEM key. Step 2 then removed the only complete copy from the file. `--from-file` stores the whole value.
- Alternative considered: Keep `<val>`.
  - Rejected: It puts the secret in the argument list.

### 4. The alert says that the copy stays
- Decision: The alert says that step 2 keeps a copy of the file, `<file>.bak-<time>`, that still holds the value. It says that a person deletes the copy by hand.
- Rationale: The audit does not scan the copy. A copy in `.devops/` or `.devcontainer/` is not git-ignored. The audit then says "verified free of plaintext secrets" while a secret stays on disk. The fix of the copy is #2645. That change removes this sentence.

### 5. The alert prints with `safe=True`
- Decision: `audit_keys_cmd` prints the alert and the line of an unaudited file with `safe=True`.
- Rationale: A section name or a directory name such as `[/x]` is markup for the terminal. Without the guard, the print raised a `MarkupError` and no alert showed.

### 6. The text of the alert is a message of `lang`
- Decision: `ConfigMessages.plaintext_alert` holds the text, and `audit_keys_cmd` formats it with the list of leaks.
- Rationale: The text belongs with the other messages of the `config` group, and a test pins it once.

## Risks / Trade-offs

- [The person runs step 2 before step 1 and loses the credential] -> The alert numbers the steps. `unset` keeps a copy of the file, and the alert says to delete the copy after the check.
- [`DEVOPS_CLI_CONFIG=<file> …` is shell syntax] -> The CLI runs on Linux, macOS and WSL shells. The error of an unknown key uses the same form.
