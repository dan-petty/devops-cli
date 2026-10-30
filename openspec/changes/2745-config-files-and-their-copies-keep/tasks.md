# Tasks

## 1. Preserve mode in _write_content

Reads: None.. Changes: None..

- [x] 1.1 Write a test in tests/config/test_config_file_mode.py that: (1) creates a config file with mode 0600, calls _write_content with new content, and asserts the resulting file has mode 0600; (2) calls _write_content for a path that does not exist and asserts the new file has mode 0600., and verify that `uv run devops ci test tests/config/test_config_file_mode.py` fails on the base
- [x] 1.2 In src/devops_cli/config/settings.py, add import stat at the top. In _write_content, after tmp.write_bytes(content) and before os.replace(tmp, dest_path), add: mode = stat.S_IMODE(dest_path.stat().st_mode) if dest_path.is_file() else 0o600, then os.chmod(tmp, mode)., and verify that `uv run devops ci test tests/config/test_config_file_mode.py` passes
- [x] 1.3 , run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Preserve mode in _copy redact path

Reads: None.. Changes: None..

- [ ] 2.1 Write a test in tests/test_config_write_history.py that: (1) creates a source file with mode 0600 and a redact key path, calls _copy(source, dest, redact), and asserts dest has mode 0600; (2) asserts the non-redact path (shutil.copy2) also preserves mode 0600., and verify that `uv run devops ci test tests/test_config_write_history.py` fails on the base
- [ ] 2.2 In src/devops_cli/config/write_history.py, add import stat at the top. In _copy, after partial.write_bytes(redacted) and before shutil.copystat(source, partial), add: os.chmod(partial, stat.S_IMODE(source.stat().st_mode))., and verify that `uv run devops ci test tests/test_config_write_history.py` passes
- [ ] 2.3 , run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
