# Design

## Context

`devops config init` is an interactive wizard. At its end it calls `save_settings` and shows the path of the config file. See `proposal.md` for the defect.

## Decisions

### 1. The command resolves the path one time and gives it to the write and to the message

`init` calls `get_active_config_path()` one time, gives the result to `save_settings` as `target_path`, and shows the same value. The write and the message cannot use different paths, because they use one value.

- **Rejected alternative: show `get_active_config_path()` after `save_settings(settings)`.** The function then runs two times. Each run reads `DEVOPS_CLI_CONFIG` and walks the directory tree again, so the message can name a different file from the written file if the environment or the tree changes between the two calls. One value removes that possibility.
- **Rejected alternative: make `save_settings` return the path that it wrote.** This changes `src/devops_cli/config/settings.py` and the signature of a function that many callers use, for one caller. `save_settings` already takes the destination as `target_path`, so the caller can know the path before the write.

## Risks / Trade-offs

- None found. Other callers of `save_settings` do not change.
