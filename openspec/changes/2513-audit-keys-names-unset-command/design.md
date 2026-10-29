# Design

## Context

See proposal.md for the background. The audit scans `config_layer_paths()` and also `config.yaml` and `.devops/config.yaml` in the current directory. `devops config unset <key>` edits `get_active_config_path()`, which is the file that `DEVOPS_CLI_CONFIG` names, else the project file, else the global file. A leak names its file as `<path>:<section>.<key>` (#2426).

## Goals / Non-Goals

**Goals:**
- Make the alert name a command that removes the leak from the file that holds it, so that the next audit passes.
- Name the same command in the help and in the generated documents.

**Non-Goals:**
- A copy of the file, which `unset` makes before it writes, still holds the plaintext value. This is a separate defect: #2645.
- Change how the audit finds a secret under a nested key (#2511).

## Decisions

### 1. The alert names the existing command with `DEVOPS_CLI_CONFIG`
- Decision: The alert names `DEVOPS_CLI_CONFIG=<file> devops config unset <key>`. No option and no code path is added.
- Rationale: The command works today for every file of the audit, and the error of an unknown key (#2201) already names it. One way to edit another file is simpler to keep than two. The command also works for a file that the audit scans but the settings do not merge, such as `config.yaml` in the current directory.
- Alternative considered: Add `--file` to `devops config unset`, as the plan of the issue proposes.
  - Rejected: `--file` and `DEVOPS_CLI_CONFIG` then do the same work, and the error of an unknown key would have to name one of them. The probe in the Feasibility section shows that the variable already removes the key and that the audit then passes.
- Alternative considered: Make `unset` remove the key from every file of `config_layer_paths()`.
  - Rejected: It does not reach `config.yaml` in the current directory, which the audit scans but `config_layer_paths()` does not name. It also removes a value that the person may want in one of the files.
- Alternative considered: Make `devops config set` of a credential remove the plaintext value from each file that holds it.
  - Rejected: `set` writes no config file by design, so a credential never goes to a file. The change would join two jobs in one command and would hide a file edit behind a store.

### 2. The alert holds a template, not one command for each leak
- Decision: The alert says that each entry reads `<file>:<key>`, and it names the command with `<file>` and `<key>`.
- Rationale: A leak is a string `<path>:<section>.<key>`. A command for each leak needs a parse of that string, and a key name can hold a colon. The template needs no parse, and it does not conflict with #2511, which changes how the audit scans keys.
- Alternative considered: Print one ready command for each leak with `shlex.quote`, as the error of an unknown key does.
  - Rejected: It needs a structured leak, which changes the scan code and the JSON report that this item does not change.

### 3. The alert asks for no value in the argument list
- Decision: The alert names `devops config set <key>`, without `<val>`. A credential then comes from a hidden prompt (`_value_or_prompt`).
- Rationale: A value in the argument list stays in the shell history and in the process list. The alert must not teach that.
- Alternative considered: Keep `<val>`.
  - Rejected: It is a defect of the old text, and `set` of a credential already asks for the value at a prompt.

### 4. The text of the alert is a message of `lang`
- Decision: `ConfigMessages.plaintext_alert` holds the text, and `audit_keys_cmd` formats it with the list of leaks.
- Rationale: The text of a command that `unset` and `set` name belongs with the other messages of the `config` group. A test then pins the text once.

## Risks / Trade-offs

- [The person runs `unset` before `set` and loses the credential] -> The alert names the commands in order and says "First" and "Then". `unset` keeps a copy of the file, and #2645 addresses what that copy holds.
- [`DEVOPS_CLI_CONFIG=<file> …` is shell syntax] -> The CLI runs on Linux, macOS and WSL shells, and the error of an unknown key uses the same form.
