"""One repository of GitHub as one value, and each name, label and key that the roadmap Service
makes for it (#4533).

`RepoRef` parses `owner/name` one time, at the edge: a setting, a command option or a webhook
payload. Its builders give the names of Jobs and Workflows, the values of labels, the names of
locks, the keys of `valkey-roadmap`, the `repo` value of a metric, the span attributes of a trace
and the parts of a clone path. ADR 0022 holds the rules.

- `key` is the casefolded `owner/name`. Data keys and telemetry use it.
- `display` is the GitHub spelling. Answers and text for people use it.
- `id` is the first 16 hex characters of the sha256 of `key`.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from opentelemetry.semconv._incubating.attributes.vcs_attributes import (
    VCS_OWNER_NAME,
    VCS_PROVIDER_NAME,
    VCS_REPOSITORY_NAME,
    VcsProviderNameValues,
)

from devops_cli.config.constants import CONST_K8S_LABEL_RE, CONST_K8S_LABEL_VALUE_RE
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import ERRORS

# The `repo` value of a metric for a repository that `service.repos` does not name.
OTHER_REPOSITORY: Final[str] = "other"

_OBJECT_PREFIX: Final[str] = "devops-cli"
_NAME_LIMIT: Final[int] = 63
_WORD_LIMIT: Final[int] = 16
_LABEL_CORE_LIMIT: Final[int] = 54
_ID_SIZE: Final[int] = 16
_LABEL_HASH_SIZE: Final[int] = 8
_UNIT_HASH_SIZE: Final[int] = 10
_RANDOM_BYTES: Final[int] = 3
_VALKEY_ROOT: Final[str] = "roadmap:v1"
_NOT_SLUG: Final = re.compile(r"[^a-z0-9]+")
_EDGES_NOT_ALNUM: Final = re.compile(r"^[^a-z0-9]+|[^a-z0-9]+$")
# The `/` that only the repository part of a key holds, and the characters that a Valkey glob
# reads as special (https://valkey.io/commands/keys/).
_NOT_IN_KEY_PART: Final = re.compile(r"[/*?\[\]\\]")


class ServiceRow(StrEnum):
    """A row of the roadmap Service that runs in a pod of its own. The value is the `<row>` of a
    unit name and of a lock name, and of the component label and the OpenTelemetry service name
    `roadmap-<row>`."""

    IMPLEMENT = "implement"
    STAGE = "stage"
    REFINE = "refine"
    ALTERNATIVES = "alternatives"
    INTAKE = "intake"
    SWEEP = "sweep"
    METRICS = "metrics"


def is_name_segment(text: str) -> bool:
    """Whether `text` is one name as GitHub and PyPI spell one: ASCII letters, digits, `-`, `_`
    and `.`, and not `.` or `..`. Such a text is one safe segment of a URL path (#2650)."""
    return text not in {"", ".", ".."} and all(
        char.isascii() and (char.isalnum() or char in "-_.") for char in text
    )


def is_repository_name(text: str) -> bool:
    """Whether `text` is `owner/name`, each part a name (`is_name_segment`)."""
    parts = text.split("/")
    return len(parts) == 2 and all(is_name_segment(part) for part in parts)


def service_key(kind: str, ident: str | None = None) -> str:
    """The `valkey-roadmap` key of state of the Service or of the installation,
    `roadmap:v1:<kind>[:<id>]`. It holds no `/`, so no pattern of a repository finds it.

    Raises:
        ValidationError: A part is empty, or holds `/` or a glob character.
    """
    return ":".join([_VALKEY_ROOT, *_key_parts(kind, ident)])


@dataclass(frozen=True, eq=False)
class RepoRef:
    """One repository of GitHub, as `owner/name` in its GitHub spelling.

    GitHub names ignore case, so two values are equal when their `key` values are equal.

    Raises:
        ValidationError: `display` is not `owner/name`, a part holds a character that a GitHub
            name does not hold or is `.` or `..`, or the owner holds a `.`.
    """

    display: str

    def __post_init__(self) -> None:
        if not is_repository_name(self.display) or "." in self.display.partition("/")[0]:
            raise ValidationError(
                ERRORS.git.repository_name_invalid.format(text=self.display[:80]),
                field="repository",
            )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RepoRef) and other.key == self.key

    def __hash__(self) -> int:
        return hash(self.key)

    @property
    def owner(self) -> str:
        """The owner in its GitHub spelling."""
        return self.display.partition("/")[0]

    @property
    def name(self) -> str:
        """The repository name in its GitHub spelling."""
        return self.display.partition("/")[2]

    @property
    def key(self) -> str:
        """The casefolded `owner/name`."""
        return self.display.casefold()

    @property
    def id(self) -> str:
        """The first 16 hex characters of the sha256 of `key`: the value of the Job label
        `implement-repo`."""
        return _digest(self.key, _ID_SIZE)

    @property
    def path_parts(self) -> tuple[str, str]:
        """The casefolded owner and name: the folders of a clone of the repository."""
        owner, _, name = self.key.partition("/")
        return owner, name

    @property
    def owner_label(self) -> str:
        """The value of the label `roadmap.devops-cli/owner`."""
        return _label_value(self.path_parts[0], self.key)

    @property
    def repo_label(self) -> str:
        """The value of the label `roadmap.devops-cli/repo`. With `owner_label` it selects this
        repository and no other."""
        return _label_value(self.path_parts[1], self.key)

    def adhoc_name(self, what: str, item: int | None = None) -> str:
        """`devops-cli-<what>-<slug of the name>[-<item>]-<6 random hex>`: a new name at each
        call, for a Job that a person starts or for the runner Job.

        Raises:
            ValidationError: `what` is not a DNS label of 16 characters or fewer.
        """
        if len(what) > _WORD_LIMIT or not CONST_K8S_LABEL_RE.fullmatch(what):
            raise ValidationError(
                ERRORS.git.repository_name_word_invalid.format(word=what[:80], limit=_WORD_LIMIT),
                field="what",
            )
        return self._object_name(what, f"{_item_tail(item)}-{secrets.token_hex(_RANDOM_BYTES)}")

    def unit_name(self, row: ServiceRow, input_key: str, item: int | None = None) -> str:
        """`devops-cli-<row>-<slug of the name>[-<item>]-<10 hex>`: the name of the one Job or
        Workflow of the row for the item and its input. The hash is of `key`, the item and
        `input_key`, so the same inputs give the same name, and a second create gets 409."""
        number = "" if item is None else str(item)
        hashed = _digest(f"{self.key}\0{number}\0{input_key}", _UNIT_HASH_SIZE)
        return self._object_name(row.value, f"{_item_tail(item)}-{hashed}")

    def lock_name(self, row: ServiceRow, item: int | None = None) -> str:
        """`<row>-<owner>.<name>[-<item>]`, casefolded: an Argo mutex name and a ConfigMap key.
        An owner holds no `.`, so the name splits at its first `.`. A row uses one form: always
        with an item, or never."""
        owner, name = self.path_parts
        return f"{row}-{owner}.{name}{_item_tail(item)}"

    def valkey_key(self, kind: str, ident: str | None = None) -> str:
        """The `valkey-roadmap` key of state of this repository,
        `roadmap:v1:<kind>:<owner>/<name>[:<id>]`, with `key` as `<owner>/<name>`.

        Raises:
            ValidationError: A part is empty, or holds `/` or a glob character.
        """
        kind_part, *ident_part = _key_parts(kind, ident)
        return ":".join([_VALKEY_ROOT, kind_part, self.key, *ident_part])

    @property
    def valkey_patterns(self) -> tuple[str, str]:
        """The two `SCAN MATCH` patterns that find each key of this repository and no other key.
        The repository part holds the only `/` of a key, and the part after it starts with `:`."""
        return f"{_VALKEY_ROOT}:*:{self.key}", f"{_VALKEY_ROOT}:*:{self.key}:*"

    def metric_value(self, configured: Collection[RepoRef]) -> str:
        """The `repo` value of a metric: `key` for a repository of `configured`, else `other`, so
        the values of the label stay a bounded set."""
        return self.key if self in configured else OTHER_REPOSITORY

    @property
    def span_attributes(self) -> dict[str, str]:
        """The OpenTelemetry VCS attributes of a span: the provider, and the casefolded owner and
        name (https://opentelemetry.io/docs/specs/semconv/registry/attributes/vcs/)."""
        owner, name = self.path_parts
        return {
            VCS_PROVIDER_NAME: VcsProviderNameValues.GITHUB.value,
            VCS_OWNER_NAME: owner,
            VCS_REPOSITORY_NAME: name,
        }

    def _object_name(self, word: str, tail: str) -> str:
        """`devops-cli-<word>-<slug of the name><tail>`, with the slug cut so that the name has 63
        characters or fewer. The prefix keeps the name in the Argo CD orphan glob `devops-cli-*`."""
        head = f"{_OBJECT_PREFIX}-{word}-"
        return head + _dns_slug(self.path_parts[1], _NAME_LIMIT - len(head) - len(tail)) + tail


def _digest(text: str, size: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:size]


def _item_tail(item: int | None) -> str:
    return "" if item is None else f"-{item}"


def _dns_slug(text: str, budget: int) -> str:
    """`text` casefolded, with each run of characters outside `[a-z0-9]` as one `-` and no `-` at
    an end, cut to `budget` characters; `x` when nothing is left."""
    slug = _NOT_SLUG.sub("-", text.casefold()).strip("-")
    return slug[: max(budget, 0)].rstrip("-") or "x"


def _label_value(part: str, key: str) -> str:
    """`part` when it is a label value. Else its alphanumeric core cut to 54 characters, then `-`
    and 8 hex of the hash of `key`; the hash alone when no core is left. A plain value is the
    exact part and a changed value holds the hash, so the pair of owner and repository values is
    exact."""
    if CONST_K8S_LABEL_VALUE_RE.fullmatch(part):
        return part
    core = _EDGES_NOT_ALNUM.sub("", part)[:_LABEL_CORE_LIMIT].rstrip("._-")
    hashed = _digest(key, _LABEL_HASH_SIZE)
    return f"{core}-{hashed}" if core else hashed


def _key_parts(kind: str, ident: str | None) -> list[str]:
    """`kind`, and `ident` when it is given, each checked as one part of a Valkey key."""
    parts = [kind] if ident is None else [kind, ident]
    for part in parts:
        if not part or _NOT_IN_KEY_PART.search(part):
            raise ValidationError(
                ERRORS.git.repository_key_part_invalid.format(part=part[:80]), field="key"
            )
    return parts
