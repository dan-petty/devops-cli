"""Review rule pack discovery, Semgrep test runner, and `rules.lock` manifest verification (#1145)."""

from __future__ import annotations

import functools
import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from devops_cli.config.commands import BIN_SEMGREP
from devops_cli.config.defaults import DEFAULT_LOCAL_BIN_DIR
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run
from devops_cli.exceptions.validation import ValidationError
from devops_cli.output.file_writer import write_text_file
from devops_cli.tools_lock import load_tools_lock

RULE_PACK_DIR = Path(__file__).resolve().parent / "rules"
RULES_LOCK_FILENAME = "rules.lock"
RULES_LOCK_PATH = RULE_PACK_DIR / RULES_LOCK_FILENAME
_TEST_SUFFIX = ".test.yaml"
_SPDX_MIT_HEADER = "# SPDX-License-Identifier: MIT"


class RuleLockEntry(BaseModel):
    """Manifest entry in `rules.lock` recording a tested pack rule's digests and Semgrep version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_file: str
    rule_sha256: str
    test_file: str
    test_sha256: str
    semgrep_version: str


class RulesLock(BaseModel):
    """The `rules.lock` manifest guarding the review rule pack."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rules: dict[str, RuleLockEntry]


def _sha256_file(path: Path) -> str:
    """Compute the hex SHA-256 digest of `path`."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_pack_rules(rules_dir: Path = RULE_PACK_DIR) -> dict[str, tuple[Path, Path]]:
    """Return `{rule_id: (rule_yaml, test_yaml)}` for every rule YAML in `rules_dir`."""
    if not rules_dir.is_dir():
        return {}
    rule_files = sorted(
        path
        for path in rules_dir.glob("*.yaml")
        if not path.name.endswith(_TEST_SUFFIX) and path.is_file()
    )
    return {path.stem: (path, rules_dir / f"{path.stem}{_TEST_SUFFIX}") for path in rule_files}


@functools.cache
def pack_rule_ids(rules_dir: Path = RULE_PACK_DIR) -> frozenset[str]:
    """Return the set of rule IDs in `rules_dir`."""
    return frozenset(discover_pack_rules(rules_dir))


def reset_rules_pack_cache() -> None:
    """Clear the cached rule pack IDs."""
    pack_rule_ids.cache_clear()


def normalize_pack_check_id(check_id: str, rules_dir: Path = RULE_PACK_DIR) -> str:
    """Strip Semgrep's directory-derived prefix when `check_id` ends with a pack rule ID."""
    tail = check_id.rsplit(".", 1)[-1]
    return tail if tail in pack_rule_ids(rules_dir) else check_id


def _validate_rule_metadata(rule_id: str, rule_doc: dict[str, Any]) -> list[str]:
    """Check a single rule mapping inside a rule YAML file."""
    problems: list[str] = []
    if rule_doc.get("id") != rule_id:
        problems.append(f"{rule_id}: rule id '{rule_doc.get('id')}' does not match filename stem")
    meta = rule_doc.get("metadata")
    if not isinstance(meta, dict):
        return [*problems, f"{rule_id}: missing metadata mapping"]
    if meta.get("license") != "MIT":
        problems.append(f"{rule_id}: metadata.license must be 'MIT'")
    cwe = meta.get("cwe")
    if not cwe or not isinstance(cwe, (list, str)):
        problems.append(f"{rule_id}: metadata.cwe is required")
    return problems


def validate_rule_pair(rule_id: str, rule_path: Path, test_path: Path) -> list[str]:
    """Validate that `rule_path` (MIT + CWE metadata) and `test_path` (`ruleid:` + `ok:`) are well-formed."""
    raw = rule_path.read_text(encoding="utf-8")
    problems: list[str] = []
    if not raw.startswith(_SPDX_MIT_HEADER):
        problems.append(f"{rule_path.name}: missing '{_SPDX_MIT_HEADER}' header")
    parsed = yaml.safe_load(raw)
    rules_list = parsed.get("rules") if isinstance(parsed, dict) else None
    if (
        not isinstance(rules_list, list)
        or len(rules_list) != 1
        or not isinstance(rules_list[0], dict)
    ):
        problems.append(f"{rule_path.name}: must define exactly one rule in 'rules'")
    else:
        problems.extend(_validate_rule_metadata(rule_id, rules_list[0]))
    if not test_path.is_file():
        return [*problems, f"{rule_id}: missing companion test file '{test_path.name}'"]
    test_text = test_path.read_text(encoding="utf-8")
    if f"ruleid: {rule_id}" not in test_text:
        problems.append(f"{test_path.name}: missing '# ruleid: {rule_id}' test annotation")
    if f"ok: {rule_id}" not in test_text:
        problems.append(f"{test_path.name}: missing '# ok: {rule_id}' test annotation")
    return problems


def pinned_semgrep_version() -> str:
    """Return the pinned Semgrep version from `tools.lock`."""
    return load_tools_lock().python["semgrep"].version


def build_rules_lock(
    rules_dir: Path = RULE_PACK_DIR,
    semgrep_version: str | None = None,
) -> RulesLock:
    """Build a `RulesLock` snapshot from the rule and test files in `rules_dir`."""
    version = semgrep_version or pinned_semgrep_version()
    entries: dict[str, RuleLockEntry] = {}
    for rule_id, (rule_path, test_path) in discover_pack_rules(rules_dir).items():
        if problems := validate_rule_pair(rule_id, rule_path, test_path):
            raise ValidationError("; ".join(problems), field="rules")
        entries[rule_id] = RuleLockEntry(
            rule_file=rule_path.name,
            rule_sha256=_sha256_file(rule_path),
            test_file=test_path.name,
            test_sha256=_sha256_file(test_path),
            semgrep_version=version,
        )
    return RulesLock(rules=entries)


def read_rules_lock(rules_dir: Path = RULE_PACK_DIR) -> RulesLock:
    """Load and validate `rules.lock` in `rules_dir`."""
    lock_path = rules_dir / RULES_LOCK_FILENAME
    try:
        return RulesLock.model_validate_json(lock_path.read_bytes())
    except (OSError, PydanticValidationError) as exc:
        raise ValidationError(f"Cannot read {lock_path}: {exc}", field="rules_lock") from exc


def _compare_lock_entry(
    rule_id: str,
    expected: RuleLockEntry,
    actual: RuleLockEntry | None,
) -> list[str]:
    """Compare one expected `RuleLockEntry` against the recorded `rules.lock` entry."""
    if actual is None:
        return [f"{rule_id}: missing from {RULES_LOCK_FILENAME}"]
    mismatches: list[str] = []
    if actual.rule_sha256 != expected.rule_sha256:
        mismatches.append(f"{rule_id}: rule_sha256 drift in {RULES_LOCK_FILENAME}")
    if actual.test_sha256 != expected.test_sha256:
        mismatches.append(f"{rule_id}: test_sha256 drift in {RULES_LOCK_FILENAME}")
    if actual.semgrep_version != expected.semgrep_version:
        mismatches.append(
            f"{rule_id}: semgrep_version '{actual.semgrep_version}' != pinned '{expected.semgrep_version}'"
        )
    return mismatches


def verify_rules_lock(
    rules_dir: Path = RULE_PACK_DIR,
    expected_version: str | None = None,
) -> list[str]:
    """Return any structural, digest, or version mismatches between `rules_dir` and `rules.lock`."""
    discovered = discover_pack_rules(rules_dir)
    if not discovered:
        return [f"No rules found in {rules_dir}"]
    problems: list[str] = []
    for rule_id, (rule_path, test_path) in discovered.items():
        problems.extend(validate_rule_pair(rule_id, rule_path, test_path))
    if problems:
        return problems
    try:
        recorded = read_rules_lock(rules_dir)
    except ValidationError as exc:
        return [exc.message]
    expected = build_rules_lock(rules_dir, semgrep_version=expected_version)
    for rule_id, exp_entry in expected.rules.items():
        problems.extend(_compare_lock_entry(rule_id, exp_entry, recorded.rules.get(rule_id)))
    stale = sorted(set(recorded.rules) - set(expected.rules))
    problems.extend(f"{rule_id}: stale entry in {RULES_LOCK_FILENAME}" for rule_id in stale)
    return problems


def _resolve_semgrep_binary() -> str:
    """Prefer the pinned binary in `~/.local/bin/semgrep` when installed, else PATH `semgrep`."""
    search_path = os.pathsep.join((str(DEFAULT_LOCAL_BIN_DIR), os.environ.get("PATH", "")))
    return shutil.which(BIN_SEMGREP, path=search_path) or BIN_SEMGREP


def _detect_semgrep_version(binary: str, env: dict[str, str]) -> str:
    """Run `semgrep --version` and return the version string."""
    res = run_subprocess([binary, "--version"], capture_output=True, env=env)
    version = (
        res.stdout.strip().splitlines()[0].strip()
        if res.returncode == 0 and res.stdout.strip()
        else ""
    )
    if not version:
        raise ValidationError(
            f"Could not determine Semgrep version from '{binary}': {(res.stderr or res.stdout).strip()[:200]}",
            field="semgrep",
        )
    return version


def run_rule_pack_tests(
    rules_dir: Path = RULE_PACK_DIR,
    *,
    check_only: bool = False,
) -> RulesLock:
    """Run `semgrep --test` on `rules_dir` and write (or `--check` verify) `rules.lock`."""
    if is_dry_run():
        return build_rules_lock(rules_dir)
    env = {**os.environ, "SEMGREP_ENABLE_VERSION_CHECK": "0"}
    binary = _resolve_semgrep_binary()
    version = _detect_semgrep_version(binary, env)
    res = run_subprocess(
        [binary, "--test", "--metrics", "off", str(rules_dir)],
        capture_output=True,
        env=env,
    )
    if res.returncode != 0:
        detail = (res.stdout or res.stderr).strip()[:240]
        raise ValidationError(f"semgrep --test failed on {rules_dir}: {detail}", field="rules")
    if check_only:
        if problems := verify_rules_lock(rules_dir, expected_version=version):
            raise ValidationError("; ".join(problems), field="rules_lock")
        return read_rules_lock(rules_dir)
    lock = build_rules_lock(rules_dir, semgrep_version=version)
    write_text_file(rules_dir / RULES_LOCK_FILENAME, lock.model_dump_json(indent=2) + "\n")
    return lock
