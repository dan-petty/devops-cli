# Design

## Overview

This change introduces declarative dry-run classification for commands in devops-cli and enforces coverage using a ratchet test.

## Component Design

### 1. Decorator and Models (`src/devops_cli/dry_run/decorator.py`)

A decorator `@dry_run_class(classification)` sets the attribute `_dry_run_class` on the target callback. Valid classifications are:
- `request-plan`: The command declares `--dry-run` and returns planned requests without executing external actions.
- `no-external-request`: The command makes no network, cluster, model, or external process calls and executes normally in dry-run mode.

A helper function `get_dry_run_class(cmd_or_callback)` resolves the classification from either a Click command or a callback function, unwrapping `__wrapped__` chains when necessary.

### 2. Lazy Proxy Dry-Run Routing (`src/devops_cli/core/command_resolver.py`)

In `resolve_proxy_dry_run`:
- If the resolved leaf command has class `no-external-request`:
  - If the command does not declare `--dry-run`, return `(True, list(args))` to execute normally without injecting `--dry-run`.
  - If the command declares `--dry-run`, forward `--dry-run` normally.
- If the command has class `request-plan` and declares `--dry-run`, forward `--dry-run`.
- If the command lacks a classification and does not declare `--dry-run`, return `(False, None)` to print the generic delegated preview message.

### 3. Ratchet Invariant Test (`tests/test_dry_run_class_ratchet.py`)

The ratchet test iterates over all command paths reachable from `devops_cli.main._COMMAND_SPECS`:
1. Every path must either possess a dry-run classification or appear in `tests/fixtures/dry_run_gaps.json`.
2. A path present in `tests/fixtures/dry_run_gaps.json` that possesses a classification triggers a test failure instructing the author to remove it.
3. An entry in `tests/fixtures/dry_run_gaps.json` that does not match a reachable command triggers a test failure.
4. A command with class `request-plan` that fails to declare `--dry-run` triggers a test failure.
5. An MCP tool in `CONST_MCP_EXPOSURE_TABLE` wrapping a `no-external-request` command must set `readOnlyHint` (`read_only=True`).
