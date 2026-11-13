"""No commit of the branch names a configured domain (SECURITY.md rule 8, #5295).

The check is the `domain` row of `devops ci` (`tests/gate/configured_domain.py`). git gives the
patch of each commit, so these cases give the check the output that `git log` prints, and no test
starts git. The configured domain of each case is `example.net`, a domain that RFC 2606 keeps for
examples, and `example.com` is the name that passes.
"""

from __future__ import annotations

import pytest

from devops_cli.config.settings import Settings
from devops_cli.core.dns_names import configured_domains
from tests.gate.configured_domain import findings, main, named_setting, outcome

_DOMAINS = {"k8s.domain": "example.net"}
_FIRST = "1" * 40
_SECOND = "2" * 40

_ADDS_A_HOST = """\
diff --git a/k8s/app.yaml b/k8s/app.yaml
new file mode 100644
index 0000000..0852260
--- /dev/null
+++ b/k8s/app.yaml
@@ -0,0 +1,3 @@
+kind: Ingress
+host: api.example.net
+port: 443
"""

_ADDS_EXAMPLE_COM_ONLY = """\
diff --git a/docs/a.md b/docs/a.md
index 1111111..2222222 100644
--- a/docs/a.md
+++ b/docs/a.md
@@ -3 +3,3 @@
-See https://api.example.net/x.
+See https://api.example.com/x.
+notexample.net and example.network
+the host example.com
"""

_ADDS_A_PATH = """\
diff --git a/k8s/grafana.example.net.yaml b/k8s/grafana.example.net.yaml
new file mode 100644
index 0000000..587be6b
--- /dev/null
+++ b/k8s/grafana.example.net.yaml
@@ -0,0 +1 @@
+kind: ConfigMap
"""

_REMOVES_A_PATH = """\
diff --git a/k8s/grafana.example.net.yaml b/k8s/grafana.example.net.yaml
deleted file mode 100644
index 587be6b..0000000
--- a/k8s/grafana.example.net.yaml
+++ /dev/null
@@ -1 +0,0 @@
-kind: ConfigMap
"""

_SHORT_HUNK = """\
diff --git a/a.txt b/a.txt
new file mode 100644
index 0000000..587be6b
--- /dev/null
+++ b/a.txt
@@ -0,0 +1,3 @@
+one
"""


def _log(*commits: tuple[str, str]) -> str:
    """The output of `git log -p --format=%x00%H` for commits given as (sha, patch)."""
    return "".join(f"\0{sha}\n\n{patch}" for sha, patch in commits)


def test_an_added_line_that_names_the_domain_is_named_by_path_line_commit_and_setting() -> None:
    """The finding names where the line is and which setting it matches, and not the value."""
    found = findings(_log((_FIRST, _ADDS_A_HOST)), _DOMAINS)

    assert (found, "example.net" in "\n".join(found)) == (
        [f"k8s/app.yaml:2 in commit {_FIRST[:12]} names the value of k8s.domain"],
        False,
    )


def test_a_commit_that_names_only_example_com_or_removes_a_name_passes() -> None:
    """A removed line, `example.com` and a name that only holds the domain as a substring give
    no finding."""
    assert findings(_log((_FIRST, _ADDS_EXAMPLE_COM_ONLY)), _DOMAINS) == []


def test_a_path_that_names_the_domain_is_named_by_its_commit_only() -> None:
    """The path of a file that names the domain is not printed, and its lines give no second
    finding."""
    domains = {"cloudflare.domain": "example.net"}

    assert findings(_log((_SECOND, _ADDS_A_PATH)), domains) == [
        f"a path in commit {_SECOND[:12]} names the value of cloudflare.domain"
    ]


def test_a_commit_that_removes_a_file_whose_path_names_the_domain_passes() -> None:
    """The removal is the fix of a path that `main` holds already, so it gives no finding."""
    assert findings(_log((_SECOND, _REMOVES_A_PATH)), _DOMAINS) == []


def test_each_commit_of_the_branch_is_read() -> None:
    """A name that one commit adds is a finding, also when a later commit removes it, because a
    push publishes each commit."""
    found = findings(_log((_SECOND, _ADDS_EXAMPLE_COM_ONLY), (_FIRST, _ADDS_A_HOST)), _DOMAINS)

    assert found == [f"k8s/app.yaml:2 in commit {_FIRST[:12]} names the value of k8s.domain"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("url: https://grafana.example.net/d/x", "k8s.domain"),
        ("EXAMPLE.NET.", "k8s.domain"),
        ("mail user@example.net", "k8s.domain"),
        ("tls: *.example.net:443", "k8s.domain"),
        ("file k8s/grafana.example.net.yaml", "k8s.domain"),
        ("notexample.net", None),
        ("my-example.net", None),
        ("example.network", None),
        ("example.com and api.example.com", None),
    ],
)
def test_a_name_is_the_domain_with_no_name_character_next_to_it(
    text: str, expected: str | None
) -> None:
    """The domain names itself in any case when no letter, digit or hyphen is next to it. A dot
    is no such character, so a name under the domain and a file name with an extension name it."""
    assert named_setting(text, _DOMAINS) == expected


@pytest.mark.parametrize("value", ["example.net.", " example.net ", "EXAMPLE.NET"])
def test_a_configured_domain_finds_its_hosts_in_each_spelling_of_the_config(value: str) -> None:
    """The config keeps a final dot and blank space, and the row reads the domain as a host name
    spells it, so `example.net.` finds `api.example.net`."""
    domains = configured_domains(Settings.model_validate({"k8s": {"domain": value}}))

    assert findings(_log((_FIRST, _ADDS_A_HOST)), domains) == [
        f"k8s/app.yaml:2 in commit {_FIRST[:12]} names the value of k8s.domain"
    ]


@pytest.mark.parametrize("value", ["bücher.example", "xn--bcher-kva.example"])
@pytest.mark.parametrize("text", ["https://bücher.example/", "api.xn--bcher-kva.example"])
def test_a_domain_with_a_unicode_label_is_found_in_its_ascii_and_its_unicode_form(
    value: str, text: str
) -> None:
    """A host name can spell a Unicode label in its ASCII form, `xn--`, or as Unicode. The row
    finds both forms, whichever form the config holds."""
    domains = configured_domains(Settings.model_validate({"cloudflare": {"domain": value}}))

    assert named_setting(text, domains) == "cloudflare.domain"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("api.k8s.example.net", "k8s.domain"), ("www.example.net", "cloudflare.domain")],
)
def test_the_first_configured_domain_that_a_name_is_under_gives_the_setting(
    text: str, expected: str
) -> None:
    """With a domain under the other, a name under both gives the setting that comes first."""
    domains = {"k8s.domain": "k8s.example.net", "cloudflare.domain": "example.net"}

    assert named_setting(text, domains) == expected


def test_the_outcome_fails_with_each_finding_and_the_counts() -> None:
    """A finding fails the row. The output names each finding and counts the findings and the
    commits."""
    assert outcome(_log((_SECOND, _ADDS_EXAMPLE_COM_ONLY), (_FIRST, _ADDS_A_HOST)), _DOMAINS) == (
        1,
        [
            f"domain: k8s/app.yaml:2 in commit {_FIRST[:12]} names the value of k8s.domain",
            "domain: the commits from origin/main to HEAD name a configured domain (findings: 1, "
            "commits: 2). Remove each name: write example.com or a role such as <domain>. Then "
            "change each commit that holds a name, because a push publishes each commit.",
        ],
    )


def test_the_outcome_passes_with_the_count_of_commits() -> None:
    """A branch with no finding passes, and the output counts the commits that the row read."""
    assert outcome(_log((_SECOND, _ADDS_EXAMPLE_COM_ONLY)), _DOMAINS) == (
        0,
        ["domain: the commits from origin/main to HEAD name no configured domain (commits: 1)."],
    )


def test_a_patch_that_unidiff_cannot_read_fails_with_no_line_of_it() -> None:
    """The error of `unidiff` can quote a line of the patch, so the row prints the count of
    commits only."""
    assert outcome(_log((_FIRST, _SHORT_HUNK)), _DOMAINS) == (
        1,
        [
            "domain: unidiff cannot read the patches of the commits from origin/main to HEAD "
            "(commits: 1)."
        ],
    )


def test_with_no_configured_domain_the_row_reads_no_commit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The config of the test sets no domain, so the row says that it read no commit, and
    passes."""
    status = main([])

    assert (status, capsys.readouterr().out) == (
        0,
        "domain: no k8s.domain or cloudflare.domain is configured, so the row read no commit\n",
    )
