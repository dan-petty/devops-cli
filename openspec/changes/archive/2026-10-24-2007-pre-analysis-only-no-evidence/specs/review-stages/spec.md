# Spec Delta

## Purpose

The stage options of `devops review path`, `branch` and `pr` decide which review stages run, and so which tools a review starts.

## ADDED Requirements

### Requirement: A review with the static scan off starts no analyzer and no evidence tool

The review SHALL start no static analyzer, no Ruff, no mypy and no tool canary when its static scan stage is off. The options `--pre-analysis-only`, `--no-static-scan` and `--reporting-only` turn the static scan stage off.

#### Scenario: A pre-analysis-only review of Python files

- **WHEN** a review runs with `--pre-analysis-only` on a tree whose Python files have the Ruff and mypy settings that the tools need
- **THEN** the review starts no static analyzer, no Ruff and no mypy, and runs no tool canary

#### Scenario: A review with no static scan

- **WHEN** a review runs with `--no-static-scan` or `--reporting-only` on the same tree
- **THEN** the review starts no static analyzer, no Ruff and no mypy, and runs no tool canary
