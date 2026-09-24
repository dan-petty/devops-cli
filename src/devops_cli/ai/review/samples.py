"""Open-source sample repositories pinned by commit, for validating devops ai beyond Python.

devops ai is meant for any technical project, but its live checks had used one Python repository
and one set of Ansible playbooks. The catalog (`samples.json`) names permissively licensed
repositories across languages and infrastructure formats, each pinned to an exact commit with
the parts of it the tooling is run over. A fetch takes only that commit, at depth one, into the
samples data directory, then checks the commit, the licence files and the paths it expects.

Fetching needs the network, so it stays out of CI; the tests fetch from local repositories.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from devops_cli.config.commands import BIN_GIT
from devops_cli.core.process import run_subprocess

CATALOG_PATH = Path(__file__).with_name("samples.json")
PERMISSIVE_LICENSES = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"})
SAMPLE_FETCH_TIMEOUT_SECONDS = 300.0
# A dual licence ("MIT OR Apache-2.0") is permissive when every licence it names is.
_SPDX_OPERATOR = re.compile(r"\s+(?:OR|AND)\s+")


class SampleCategory(StrEnum):
    """The kinds of technical project the samples cover."""

    PYTHON = "python"
    TYPESCRIPT_JAVASCRIPT = "typescript-javascript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSHARP_DOTNET = "csharp-dotnet"
    C_CPP = "c-cpp"
    TERRAFORM = "terraform"
    KUBERNETES_HELM = "kubernetes-helm"
    DOCKERFILE = "dockerfile"
    SHELL = "shell"
    DOCUMENTATION = "documentation"


class SampleRepository(BaseModel):
    """One repository at one commit, and the parts of it the tooling is run over."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    category: SampleCategory
    languages: list[str] = Field(min_length=1)
    repository: str
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    license: str
    license_files: list[str] = Field(min_length=1)
    paths: list[str] = Field(min_length=1)

    @field_validator("repository")
    @classmethod
    def _https_or_local(cls, value: str) -> str:
        """HTTPS for the catalog; a local repository for tests and mirrors."""
        if not value.startswith(("https://", "file://")):
            raise ValueError(f"repository must be an https:// or file:// URL: {value}")
        return value

    @field_validator("license")
    @classmethod
    def _permissive(cls, value: str) -> str:
        licenses = set(_SPDX_OPERATOR.split(value.strip()))
        if not licenses <= PERMISSIVE_LICENSES:
            raise ValueError(f"not a permissive licence: {value}")
        return value

    @field_validator("license_files", "paths")
    @classmethod
    def _inside_the_repository(cls, values: list[str]) -> list[str]:
        for value in values:
            path = PurePosixPath(value)
            if not value or path.is_absolute() or ".." in path.parts:
                raise ValueError(f"path must be relative to the repository: {value!r}")
        return values


class SampleCatalog(BaseModel):
    """The checked-in catalog of sample repositories."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    about: str = ""
    samples: list[SampleRepository]

    @model_validator(mode="after")
    def _unique_names(self) -> SampleCatalog:
        names = [sample.name for sample in self.samples]
        if duplicates := sorted({name for name in names if names.count(name) > 1}):
            raise ValueError(f"sample names must be unique: {duplicates}")
        return self

    def select(
        self,
        names: Sequence[str] | None = None,
        categories: Sequence[SampleCategory] | None = None,
    ) -> list[SampleRepository]:
        """The samples named, or all of them, within the categories given, if any."""
        unknown = sorted(set(names or []) - {sample.name for sample in self.samples})
        if unknown:
            raise ValueError(f"no sample named {', '.join(unknown)}")
        return [
            sample
            for sample in self.samples
            if (not names or sample.name in names)
            and (not categories or sample.category in categories)
        ]


def load_sample_catalog(path: Path = CATALOG_PATH) -> SampleCatalog:
    """Load and validate the sample catalog."""
    return SampleCatalog.model_validate_json(path.read_text(encoding="utf-8"))


def samples_dir() -> Path:
    """The directory samples are fetched into, one subdirectory per sample."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    env_data_dir = os.environ.get("DEVOPS_CLI_DATA_DIR")
    directory = Path(env_data_dir) / "samples" if env_data_dir else load_settings().data.samples_dir
    return resolve_data_path(directory)


def _git(checkout: Path, *args: str) -> tuple[int, str]:
    """Run git in a checkout, never prompting for credentials; its exit code and output."""
    proc = run_subprocess(
        [BIN_GIT, "-C", str(checkout), *args],
        env={"GIT_TERMINAL_PROMPT": "0"},
        timeout=SAMPLE_FETCH_TIMEOUT_SECONDS,
        quiet=True,
    )
    return proc.returncode, (proc.stdout or proc.stderr or "").strip()


def checkout_problems(sample: SampleRepository, checkout: Path) -> list[str]:
    """Why a checkout does not match its catalog entry; empty when it does."""
    if not (checkout / ".git").exists():
        return ["not fetched"]
    code, head = _git(checkout, "rev-parse", "HEAD")
    problems = [] if code == 0 and head == sample.commit else [f"not at {sample.commit[:12]}"]
    problems += [
        f"licence file {name} is missing"
        for name in sample.license_files
        if not (checkout / name).is_file()
    ]
    problems += [
        f"path {path} is missing" for path in sample.paths if not (checkout / path).exists()
    ]
    return problems


def fetch_sample(sample: SampleRepository, root: Path) -> list[str]:
    """Fetch a sample at its pinned commit into `root/<name>`; why it is wrong, or nothing.

    Only that commit is fetched, at depth one. A checkout already at the commit is left alone,
    and one at another commit is moved to it.
    """
    checkout = root / sample.name
    if not checkout_problems(sample, checkout):
        return []
    if not (checkout / ".git").exists():
        checkout.mkdir(parents=True, exist_ok=True)
        _git(checkout, "init", "--quiet")
    code, output = _git(
        checkout, "fetch", "--quiet", "--depth", "1", sample.repository, sample.commit
    )
    if code != 0:
        return [f"fetch failed: {output.splitlines()[-1] if output else f'exit {code}'}"]
    code, output = _git(checkout, "checkout", "--quiet", "--force", "--detach", "FETCH_HEAD")
    if code != 0:
        return [f"checkout failed: {output.splitlines()[-1] if output else f'exit {code}'}"]
    return checkout_problems(sample, checkout)


__all__ = [
    "CATALOG_PATH",
    "PERMISSIVE_LICENSES",
    "SampleCatalog",
    "SampleCategory",
    "SampleRepository",
    "checkout_problems",
    "fetch_sample",
    "load_sample_catalog",
    "samples_dir",
]
