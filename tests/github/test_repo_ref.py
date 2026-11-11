"""`RepoRef`: one repository of GitHub, and the names, labels and keys that come from it (#4533).

The properties hold for any `owner/name` that GitHub can spell. The rules are in
`docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md`.
"""

from __future__ import annotations

import re
import string

import pytest
from fakeredis import FakeServer
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from devops_cli.config.constants import CONST_K8S_LABEL_RE, CONST_K8S_LABEL_VALUE_RE
from devops_cli.exceptions import ValidationError
from devops_cli.github.repo_ref import (
    OTHER_REPOSITORY,
    RepoRef,
    ServiceRow,
    is_name_segment,
    is_repository_name,
    service_key,
)
from devops_cli.k8s.cluster_job import repository_label
from tests.support.fakes.valkey import valkey_client_on

# GitHub logins hold letters, digits and `-`; the parser also takes `_`, as GitHub's own checks
# of a repository path do. A repository name also holds `.`.
_OWNERS = st.text(alphabet=string.ascii_letters + string.digits + "-_", min_size=1, max_size=39)
_NAMES = st.text(
    alphabet=string.ascii_letters + string.digits + "-_.", min_size=1, max_size=100
).filter(lambda name: name not in {".", ".."})
_REPOS = st.builds(lambda owner, name: RepoRef(f"{owner}/{name}"), _OWNERS, _NAMES)
_ITEMS = st.none() | st.integers(min_value=1, max_value=2**31 - 1)
_INPUT_KEYS = st.text(max_size=80)
# Kinds and ids of `valkey-roadmap` keys, in the forms of the key table of the move of the
# Service work: words with `:` between them, numbers, hashes and uids.
_KEY_PARTS = st.text(
    alphabet=string.ascii_lowercase + string.digits + ":-_.", min_size=1, max_size=20
)
_CONFIGMAP_KEY = re.compile(r"[-._a-zA-Z0-9]+")
_HEX = re.compile(r"[0-9a-f]+")

# Shapes of the live repositories (counts and lengths only): one owner, full names of 15 to 31
# characters, one name with a `.`.
_LIVE_SHAPES = (
    "example-owner/devops-cli",
    "example-owner/homelab",
    "example-owner/notes.example",
    "example-owner/service-catalogue",
)


@given(repo=_REPOS)
def test_each_label_value_of_a_repository_is_a_kubernetes_label_value(repo: RepoRef) -> None:
    assert CONST_K8S_LABEL_VALUE_RE.fullmatch(repo.owner_label)
    assert CONST_K8S_LABEL_VALUE_RE.fullmatch(repo.repo_label)


@pytest.mark.parametrize("text", _LIVE_SHAPES)
def test_a_part_that_is_a_label_value_is_the_label_value_with_no_hash(text: str) -> None:
    repo = RepoRef(text)

    assert (repo.owner_label, repo.repo_label) == tuple(text.split("/"))


def test_a_label_value_is_the_casefolded_part() -> None:
    repo = RepoRef("Example-Owner/My.Repo_Name")

    assert (repo.owner_label, repo.repo_label) == ("example-owner", "my.repo_name")


@pytest.mark.parametrize(
    ("text", "core"),
    [
        pytest.param("o/.github", "github", id="leading-dot"),
        pytest.param("o/repo_", "repo", id="trailing-underscore"),
        pytest.param("o/" + "a" * 100, "a" * 54, id="too-long"),
        pytest.param("o/__", "", id="no-alphanumeric"),
    ],
)
def test_a_part_that_is_no_label_value_gets_a_cut_value_and_the_hash_of_the_key(
    text: str, core: str
) -> None:
    repo = RepoRef(text)
    hashed = repo.id[:8]

    assert repo.repo_label == (f"{core}-{hashed}" if core else hashed)


def test_an_owner_that_is_no_label_value_gets_the_hash_of_the_key() -> None:
    repo = RepoRef("-owner-/name")

    assert repo.owner_label == f"owner-{repo.id[:8]}"


@given(repo=_REPOS, what=st.sampled_from(["implement", "job"]), item=_ITEMS)
def test_an_ad_hoc_name_is_a_dns_label_of_63_characters_or_fewer(
    repo: RepoRef, what: str, item: int | None
) -> None:
    name = repo.adhoc_name(what, item)

    assert CONST_K8S_LABEL_RE.fullmatch(name)
    assert name.startswith(f"devops-cli-{what}-")


def test_two_ad_hoc_names_of_one_repository_differ() -> None:
    repo = RepoRef("example-owner/devops-cli")

    assert repo.adhoc_name("implement", 7) != repo.adhoc_name("implement", 7)


@pytest.mark.parametrize("what", ["", "Implement", "a-very-long-word-for-a-job"])
def test_an_ad_hoc_name_refuses_a_word_that_is_no_short_dns_label(what: str) -> None:
    with pytest.raises(ValidationError, match="is not a DNS label"):
        RepoRef("o/n").adhoc_name(what)


@given(repo=_REPOS, row=st.sampled_from(ServiceRow), item=_ITEMS, input_key=_INPUT_KEYS)
def test_a_unit_name_is_a_dns_label_of_63_characters_or_fewer_in_the_argo_cd_glob(
    repo: RepoRef, row: ServiceRow, item: int | None, input_key: str
) -> None:
    name = repo.unit_name(row, input_key, item)

    assert CONST_K8S_LABEL_RE.fullmatch(name)
    assert name.startswith(f"devops-cli-{row}-")


@given(name=_NAMES, row=st.sampled_from(ServiceRow), item=_ITEMS, input_key=_INPUT_KEYS)
def test_a_unit_name_comes_only_from_its_inputs_and_not_from_the_spelling(
    name: str, row: ServiceRow, item: int | None, input_key: str
) -> None:
    upper = RepoRef(f"Owner/{name.upper()}")
    lower = RepoRef(f"owner/{name.lower()}")

    assert upper.unit_name(row, input_key, item) == lower.unit_name(row, input_key, item)


def test_a_unit_name_changes_with_its_input_key() -> None:
    repo = RepoRef("example-owner/devops-cli")

    assert repo.unit_name(ServiceRow.STAGE, "a", 1) != repo.unit_name(ServiceRow.STAGE, "b", 1)


def test_a_long_name_is_cut_so_the_longest_row_with_a_long_item_fills_63_characters() -> None:
    name = RepoRef("example-owner/" + "a" * 40).unit_name(
        ServiceRow.ALTERNATIVES, "k" * 64, 999_999
    )

    assert (len(name), name.startswith("devops-cli-alternatives-" + "a" * 21 + "-999999-")) == (
        63,
        True,
    )


@given(first=_REPOS, second=_REPOS, row=st.sampled_from(ServiceRow), item=_ITEMS)
def test_two_repositories_get_two_ids_and_two_unit_names(
    first: RepoRef, second: RepoRef, row: ServiceRow, item: int | None
) -> None:
    assume(first != second)

    assert first.id != second.id
    assert first.unit_name(row, "key", item) != second.unit_name(row, "key", item)


@given(repo=_REPOS)
def test_the_id_is_the_value_of_the_implement_repo_label_of_today(repo: RepoRef) -> None:
    assert (len(repo.id), bool(_HEX.fullmatch(repo.id))) == (16, True)
    assert repo.id == repository_label(repo.display)


@given(repo=_REPOS, row=st.sampled_from(ServiceRow), item=_ITEMS)
def test_each_lock_name_is_a_configmap_key(
    repo: RepoRef, row: ServiceRow, item: int | None
) -> None:
    assert _CONFIGMAP_KEY.fullmatch(repo.lock_name(row, item))


@given(
    first=_REPOS, second=_REPOS, row=st.sampled_from(ServiceRow), items=st.tuples(_ITEMS, _ITEMS)
)
def test_two_repositories_get_two_lock_names_in_one_form(
    first: RepoRef, second: RepoRef, row: ServiceRow, items: tuple[int | None, int | None]
) -> None:
    assume((first, items[0]) != (second, items[1]))
    assume((items[0] is None) == (items[1] is None))

    assert first.lock_name(row, items[0]) != second.lock_name(row, items[1])


def test_a_lock_name_joins_the_casefolded_owner_and_name_with_a_dot() -> None:
    repo = RepoRef("Example-Owner/Devops-CLI")

    assert (repo.lock_name(ServiceRow.INTAKE), repo.lock_name(ServiceRow.REFINE, 42)) == (
        "intake-example-owner.devops-cli",
        "refine-example-owner.devops-cli-42",
    )


@settings(max_examples=50)
@given(
    first=_REPOS,
    second=_REPOS,
    parts=st.lists(st.tuples(_KEY_PARTS, st.none() | _KEY_PARTS), min_size=1, max_size=4),
)
def test_the_two_patterns_of_a_repository_find_all_its_keys_and_no_other_key(
    first: RepoRef, second: RepoRef, parts: list[tuple[str, str | None]]
) -> None:
    own = {first.valkey_key(kind, ident) for kind, ident in parts}
    other = {second.valkey_key(kind, ident) for kind, ident in parts}
    installation = {service_key(kind, ident) for kind, ident in parts}
    valkey = valkey_client_on(FakeServer(server_type="valkey"))
    for key in own | other | installation:
        valkey.set(key, "1")

    found = {key for pattern in first.valkey_patterns for key in valkey.keys(pattern)}

    assert found == own


def test_a_repository_key_holds_the_casefolded_key_after_the_kind() -> None:
    repo = RepoRef("Example-Owner/Devops-CLI")

    assert (repo.valkey_key("plan", "12"), repo.valkey_key("sched")) == (
        "roadmap:v1:plan:example-owner/devops-cli:12",
        "roadmap:v1:sched:example-owner/devops-cli",
    )


def test_an_installation_key_holds_no_repository() -> None:
    assert (service_key("halt", "123"), service_key("sentinel")) == (
        "roadmap:v1:halt:123",
        "roadmap:v1:sentinel",
    )


@pytest.mark.parametrize(
    ("kind", "ident"),
    [
        pytest.param("plan", "a/b", id="slash-in-id"),
        pytest.param("pl/an", None, id="slash-in-kind"),
        pytest.param("plan*", None, id="glob-in-kind"),
        pytest.param("plan", "[1]", id="glob-in-id"),
        pytest.param("", None, id="empty-kind"),
        pytest.param("plan", "", id="empty-id"),
    ],
)
def test_a_key_part_that_could_match_another_repository_is_refused(
    kind: str, ident: str | None
) -> None:
    with pytest.raises(ValidationError, match="is empty or holds"):
        RepoRef("o/n").valkey_key(kind, ident)
    with pytest.raises(ValidationError, match="is empty or holds"):
        service_key(kind, ident)


@pytest.mark.parametrize(
    "text",
    ["", "o", "o/n/x", "o.x/n", "o/..", "o/.", "/n", "o/", "ö/n", "o/n ", " o/n"],
)
def test_text_that_is_not_owner_name_is_refused(text: str) -> None:
    with pytest.raises(ValidationError, match="owner/name"):
        RepoRef(text)


def test_a_name_that_starts_with_a_dot_is_a_repository() -> None:
    assert RepoRef("o/.github").key == "o/.github"


def test_two_spellings_are_one_repository_that_keeps_its_github_spelling() -> None:
    upper, lower = RepoRef("Owner/Repo"), RepoRef("owner/repo")

    assert (upper == lower, hash(upper) == hash(lower), upper.display) == (True, True, "Owner/Repo")
    assert (upper.owner, upper.name, upper.key) == ("Owner", "Repo", "owner/repo")


def test_the_metric_value_is_the_key_of_a_configured_repository_and_other_else() -> None:
    configured = frozenset({RepoRef("Owner/Repo")})

    assert (
        RepoRef("owner/REPO").metric_value(configured),
        RepoRef("owner/else").metric_value(configured),
    ) == ("owner/repo", OTHER_REPOSITORY)


def test_the_span_attributes_name_github_and_the_casefolded_owner_and_name() -> None:
    assert RepoRef("Owner/Repo").span_attributes == {
        "vcs.provider.name": "github",
        "vcs.owner.name": "owner",
        "vcs.repository.name": "repo",
    }


def test_the_path_parts_are_the_casefolded_owner_and_name() -> None:
    assert RepoRef("Owner/.Repo").path_parts == ("owner", ".repo")


@pytest.mark.parametrize(
    ("text", "segment", "repository"),
    [
        pytest.param("devops-cli", True, False, id="name"),
        pytest.param("owner/name", False, True, id="repository"),
        pytest.param("..", False, False, id="dot-dot"),
        pytest.param("a b", False, False, id="space"),
        pytest.param("o/n/x", False, False, id="three-parts"),
    ],
)
def test_a_name_segment_and_a_repository_name_hold_only_github_name_characters(
    text: str, segment: bool, repository: bool
) -> None:
    assert (is_name_segment(text), is_repository_name(text)) == (segment, repository)
