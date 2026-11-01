### Problem Description

A config file that devops-cli writes, the copies of it and the temporary file of a write get their mode from the default umask, usually 0644. A config file can hold secrets, so the files are readable by other users of the host.

Two cases show this, found while the change for #2645 was built:

1. A write replaces the live file with a new file: `_write_content` in `src/devops_cli/config/settings.py` writes `<name>.yaml.tmp` with `write_bytes` and calls `os.replace`. The new file has the umask mode, so a config file that a person set to 0600 becomes 0644 after any `devops config set` or `devops config unset`. The copy keeps the old mode, because `shutil.copy2` copies it, so the copy is then more closed than the live file.
2. The temporary file that `_copy` in `src/devops_cli/config/write_history.py` writes for a redacted copy exists with the umask mode until `shutil.copystat` runs. For that moment the temporary file is more open than the live file it comes from. The same holds for the temporary file of `_write_content`.

### Reproduction Steps

1. Make a temporary `HOME`. Write `ai:` and `  model: m` to `$HOME/.config/devops-cli/config.yaml`. Run `chmod 600` on it.
2. Set `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`. Unset `DEVOPS_CLI_CONFIG`. Run `devops config unset ai.model` in a directory with no project config file.
3. Run `stat -c '%a %n' $HOME/.config/devops-cli/*`.

### Expected vs Actual Behavior

Expected: the live file keeps its mode (0600). A new config file, a copy and a temporary file are created with a mode of 0600 or the mode of the file they replace, never more open.

Actual: the live file is 0644 after the write, and the copy is 0600.

### Environment Diagnostics

devops-cli 0.21.3 at origin/main ae446f0f, Linux.

### Logs, Traces, or Terminal Output

```text
600 <tmp>/home/.config/devops-cli/config.yaml          (before)
644 <tmp>/home/.config/devops-cli/config.yaml          (after)
600 <tmp>/home/.config/devops-cli/config.yaml.bak-<stamp>
```

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=07fb4c222b09ef6bb9e6fc9cd1d5fbb45f6c9a78 -->
## Proposed design

### Problem statement
A config file that devops-cli writes gets the default umask mode, usually 0644, instead of the mode of the file it replaces. A config file can hold secrets, so other users of the host can read it. Two code paths cause this: _write_content in settings.py creates a tmp file with write_bytes and calls os.replace, so the live file loses its mode. _copy in write_history.py creates a tmp file with write_bytes and calls shutil.copystat after the write, so the tmp file is briefly more open than the source.

### Acceptance criteria

### Requirement: Preserve existing file mode
A write of a config file that already exists MUST preserve the mode of the existing file.

#### Scenario: Write to a 0600 file
- **WHEN** A config file with mode 0600 is written by devops config set or devops config unset
- **THEN** The resulting file has mode 0600

### Requirement: New file gets mode 0600
A config file that does not exist and is created by a write MUST be created with mode 0600.

#### Scenario: Create a new config file
- **WHEN** A write creates a config file that did not exist before
- **THEN** The new file has mode 0600

### Requirement: Backup copy keeps source mode
A backup copy of a config file MUST have the same mode as the source file.

#### Scenario: Copy a 0600 file
- **WHEN** A backup copy is made of a config file with mode 0600
- **THEN** The copy has mode 0600

### Requirement: Temporary file never more open
A temporary file written during a config write MUST have a mode no more open than the file it replaces, or 0600 when no file exists.

#### Scenario: Tmp file mode during write
- **WHEN** A temporary file is created during a config write
- **THEN** The temporary file has mode 0600 or the mode of the file it replaces

### Existing Tool Considered
No check has run. The Python standard library covers the need: os.open with a mode argument, os.chmod, and shutil.copy2 all set a file's mode. The project's code uses Path.write_bytes, which does not set the mode, and the fix is to set the mode on the tmp file before os.replace. No external tool or library is needed. The written cost is a few lines in two functions and their tests.

### Key questions
- **What mode should a new config file get when no existing file provides a mode?**: 0600. The issue states that a new config file is created with a mode of 0600, never more open. A config file can hold secrets, so owner read/write only is the correct default. (best practice) [sources: src/devops_cli/config/settings.py, src/devops_cli/config/write_history.py]
  - Chosen: 0600. Owner read/write only. Matches the issue's expected behavior and the security need for files that hold secrets.
  - Rejected: 0644 (umask default). World-readable. Insecure for files that can hold secrets. This is the current buggy behavior.
- **How should _write_content preserve the mode of the file it replaces?**: Read the existing file's mode with os.stat, set it on the tmp file with os.chmod before os.replace. When the file does not exist, set the tmp file's mode to 0600. This way the file is never visible with the wrong mode. (best practice) [sources: src/devops_cli/config/settings.py]
  - Chosen: os.chmod on tmp before os.replace. The tmp file has the correct mode before it becomes the live file. No window of wrong mode.
  - Rejected: shutil.copystat after os.replace. The live file briefly has the umask mode between os.replace and copystat. A window of wrong mode.
- **How should _copy in write_history.py fix the tmp file mode in the redact path?**: Set the tmp file's mode to the source file's mode before writing content. Use os.open with the source mode, or os.chmod immediately after creation and before write_bytes. This removes the window where the tmp file has the umask mode. (best practice) [sources: src/devops_cli/config/write_history.py]
  - Chosen: Set mode before writing content. The tmp file has the correct mode from creation. No window of wrong mode.
  - Rejected: shutil.copystat after write_bytes (current). The tmp file has the umask mode between write_bytes and copystat. A window of wrong mode.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P1-High", "Status": "In Review", "Value": "High", "implement.branch": "fix/2745-config-files-and-their-copies-keep", "implement.group": "1", "implement.job": "devops-cli-runner-20261030-203414-7d1e", "implement.job_state": "succeeded", "implement.pr": "2801", "implement.sha": "f421cf93a5c9727262c312ced7134206a6e2e98b", "implement.spend": "{\"requests\": 72, \"input_tokens\": 1537414, \"output_tokens\": 17156}", "implement.stopped": "group 2", "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "d8abdda10f147f588ba447038b0a9ea921ceca786da633a76213ed936c6464d2", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "7bba70c58996053fd82568716f133bbef8db26c2848e07bd5917b1277681b71f", "stage.branch": null, "stage.groups": null, "stage.needs_split": null, "stage.pr": null, "stage.sha": null} -->
