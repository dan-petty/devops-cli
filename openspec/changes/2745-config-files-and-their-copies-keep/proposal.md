# Proposal

## Why

#2745 reports that a config file set to 0600 becomes 0644 after any devops config set or unset, and that a temporary file in the redact path is briefly world-readable. A config file can hold secrets, so other users of the host can read it.

## What Changes

- Set the mode of the tmp file to the existing file's mode (or 0600) before os.replace in _write_content in settings.py
- Set the mode of the tmp file to the source file's mode before os.replace in _copy in write_history.py
- Add tests that assert the mode of written files, new files, and backup copies
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: Preserve existing file mode on write, New config file gets mode 0600, Backup copy keeps source mode, Temporary file never more open than source

## Impact

None.

## Feasibility

- The code in src/devops_cli/config/settings.py confirms _write_content calls tmp.write_bytes(content) then os.replace(tmp, dest_path) with no mode setting between them.
- The code in src/devops_cli/config/write_history.py confirms _copy calls partial.write_bytes(redacted) then shutil.copystat(source, partial) then os.replace(partial, dest), leaving a window where the tmp file has the umask mode.
- The issue's reproduction steps are consistent with this code: a 0600 file becomes 0644 after a write because os.replace preserves the tmp file's umask mode.
- First checks the implementation runs: uv run devops ci test tests/config/test_config_file_mode.py and uv run devops ci test tests/test_config_write_history.py

## Existing Tool Considered

The Python standard library covers the need: os.chmod sets a file's mode, os.stat reads it, and stat.S_IMODE extracts the permission bits. No external tool or library is needed. The written cost is two lines of os.chmod in two functions and their tests.
