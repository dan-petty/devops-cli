"""Tests for renovate_token rules (#6020)."""

from __future__ import annotations

from devops_cli.k8s.renovate_token import RENOVATE_TOKEN_PATH, token_file_problems


def test_renovate_token_path_constant() -> None:
    assert RENOVATE_TOKEN_PATH == "/token/github-token"


def test_token_file_problems_valid_script() -> None:
    valid_script = """
    const { readFileSync, unlinkSync } = require('node:fs');
    const token = readFileSync(process.env.DEVOPS_CLI_TOKEN_FILE ?? '/token/github-token', 'utf8');
    unlinkSync(process.env.DEVOPS_CLI_TOKEN_FILE ?? '/token/github-token');
    module.exports = { 'token': token };
    """
    assert token_file_problems(valid_script) == []


def test_token_file_problems_missing_path() -> None:
    script = "const token = readFileSync('/custom/path', 'utf8'); unlinkSync('/custom/path');"
    problems = token_file_problems(script)
    assert any("does not name the default token path" in p for p in problems)


def test_token_file_problems_missing_read() -> None:
    script = "const token = '/token/github-token'; unlinkSync('/token/github-token');"
    problems = token_file_problems(script)
    assert any("does not read" in p for p in problems)


def test_token_file_problems_missing_unlink() -> None:
    script = "const token = readFileSync('/token/github-token', 'utf8');"
    problems = token_file_problems(script)
    assert any("does not remove" in p for p in problems)


def test_token_file_problems_unlink_before_read() -> None:
    script = "unlinkSync('/token/github-token'); const token = readFileSync('/token/github-token', 'utf8');"
    problems = token_file_problems(script)
    assert any("removes /token/github-token before the read" in p for p in problems)
