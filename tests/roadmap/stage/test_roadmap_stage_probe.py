"""The premise probe of the stage job: bounded read-only git commands at the staging commit (#3011)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_DEFINITION_READ_FILES,
    CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS,
)
from devops_cli.roadmap.refine.refine import git_result
from devops_cli.roadmap.stage import stage_probe
from devops_cli.roadmap.stage.stage_probe import (
    blocked_by,
    check_claims,
    claimed_missing_checks,
    probe_premise,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.roadmap_stage import StageRepo

LIVE = "src/devops_cli/live.py"
GONE = "src/devops_cli/gone.py"
TEST_SAMPLE = "tests/test_sample.py"
LIVE_SOURCE = "def keep_comment(comments):\n    return comments[:-1]\n\nLIMIT = 3\n"
GONE_SOURCE = "def validate_url(url):\n    return url\n"
TEST_SAMPLE_SOURCE = (
    "from devops_cli.live import keep_comment\n\ndef test_keep():\n    keep_comment([])\n"
)
MODEL = "src/devops_cli/model.py"
MODEL_SOURCE = "class PullStatus:\n    labels: tuple[str, ...] = ()\n    state: str = ''\n"


@pytest.fixture
def repo(stage_repo: StageRepo) -> StageRepo:
    """A repository where `gone.py` (with `validate_url`) was added and then deleted."""
    stage_repo.track({LIVE: LIVE_SOURCE, GONE: GONE_SOURCE, TEST_SAMPLE: TEST_SAMPLE_SOURCE})
    stage_repo.git("rm", "-q", GONE)
    stage_repo.git("commit", "-q", "-m", "remove the url check")
    stage_repo.git("push", "-q", "origin", "main")
    return stage_repo


def _probe(repo: StageRepo, body: str) -> stage_probe.Probe:
    return probe_premise(repo.clone, repo.git("rev-parse", "HEAD"), body)


def test_a_present_path_and_a_defined_identifier_are_confirmed(repo: StageRepo) -> None:
    probe = _probe(repo, f"Change `{LIVE}` and `keep_comment`.")

    assert f"The path `{LIVE}` is a file of the staging commit." in probe.text
    assert f"`keep_comment` is defined at {LIVE}:1" in probe.text
    assert probe.missing == ()
    assert probe.skipped == ()


def test_the_probe_names_the_test_module_of_a_cited_function(repo: StageRepo) -> None:
    probe = _probe(repo, "Fix `keep_comment`.")

    assert "tests/test_sample.py" in probe.text


def test_the_probe_states_when_no_test_module_names_a_function(repo: StageRepo) -> None:
    probe = _probe(repo, "Fix `LIMIT`.")

    assert "No test module names `LIMIT`." in probe.text


def test_the_probe_states_when_the_bound_leaves_the_test_module_listing_out(
    repo: StageRepo,
) -> None:
    paths = {f"src/devops_cli/p{i}.py": "x = 1\n" for i in range(9)}
    repo.track(paths)
    body = " ".join(f"`{p}`" for p in paths) + " `keep_comment`"

    probe = _probe(repo, body)

    assert "The bound left the test module listing out." in probe.text


def test_a_constant_counts_as_a_definition(repo: StageRepo) -> None:
    probe = _probe(repo, "Raise `LIMIT` to 5.")

    assert f"`LIMIT` is defined at {LIVE}:4" in probe.text


SCOUT = "src/scout.rs"
SCOUT_SOURCE = "#[test]\nfn scout_reaches_target() {\n    assert!(true);\n}\n"


def test_a_rust_function_counts_as_a_definition(repo: StageRepo) -> None:
    repo.track({SCOUT: SCOUT_SOURCE})

    probe = _probe(repo, "Fix `scout_reaches_target`.")

    assert f"`scout_reaches_target` is defined at {SCOUT}:2" in probe.text
    assert probe.missing == ()


def test_an_identifier_that_the_bound_leaves_undecided_is_not_probed(repo: StageRepo) -> None:
    names = {f"src/devops_cli/f{i}.py": "x = 1\n" for i in range(9)}
    repo.track({**names, SCOUT: SCOUT_SOURCE})
    body = " ".join(f"`{name}`" for name in names) + " `scout_reaches_target`"

    probe = _probe(repo, body)

    assert (probe.commands, probe.missing, probe.skipped) == (10, (), ("scout_reaches_target",))


def test_a_cut_definition_read_leaves_the_function_not_probed(repo: StageRepo) -> None:
    callers = {
        f"src/a{n:02}.rs": f"fn caller_{n}() {{\n    shared_helper();\n}}\n"
        for n in range(CONST_ROADMAP_DEFINITION_READ_FILES + 1)
    }
    repo.track({**callers, "src/z_util.rs": "pub fn shared_helper() {}\n"})

    probe = _probe(repo, "Fix `shared_helper`.")

    assert (probe.missing, probe.skipped) == ((), ("shared_helper",))
    assert "has no definition" not in probe.text


def test_a_deleted_path_names_the_commit_that_deleted_it(repo: StageRepo) -> None:
    probe = _probe(repo, f"Fix `{GONE}`.")

    assert f"The path `{GONE}` is no file of the staging commit." in probe.text
    assert "remove the url check" in probe.text
    assert probe.missing == (GONE,)


def test_a_path_that_no_commit_held_says_so(repo: StageRepo) -> None:
    probe = _probe(repo, "Add `src/devops_cli/never.py`.")

    assert "No commit in the history deleted or renamed it." in probe.text
    assert probe.missing == ("src/devops_cli/never.py",)


def test_a_cited_bare_name_names_the_file_under_a_folder(repo: StageRepo) -> None:
    under_folder = "src/devops_cli/roadmap/stage/stage_specs.py"
    repo.track({under_folder: "def read_base():\n    return {}\n"})

    probe = _probe(repo, "Change `stage_specs.py`.")

    assert "The path `stage_specs.py` is no file at the root of the staging commit." in probe.text
    assert f"These files of the commit are candidates: `{under_folder}`." in probe.text
    assert "No commit in the history deleted or renamed it." in probe.text
    assert probe.missing == ("stage_specs.py",)


def test_a_cited_root_file_lists_no_same_name_file(repo: StageRepo) -> None:
    repo.track({"README.md": "# Read me\n"})

    probe = _probe(repo, "Change `README.md`.")

    assert probe.lines == ("The path `README.md` is a file of the staging commit.",)
    assert probe.missing == ()


def test_a_cited_bare_name_names_at_most_five_same_name_files(repo: StageRepo) -> None:
    folders = "abcde"
    names = {f"src/{folder}/same_name.py": "x = 1\n" for folder in folders}
    repo.track({**names, "src/f/same_name.py": "x = 1\n"})

    probe = _probe(repo, "Change `same_name.py`.")

    candidates = [path for path in names if path in probe.text]
    assert candidates == sorted(names)
    assert "src/f/same_name.py" not in probe.text


def test_the_replay_of_2971_names_the_commit_that_removed_validate_url(repo: StageRepo) -> None:
    probe = _probe(repo, "The check `validate_url` rejects a private address.")

    assert "`validate_url` has no definition at the staging commit." in probe.text
    assert "remove the url check" in probe.text
    assert probe.missing == ("validate_url",)


def test_an_identifier_that_no_commit_held_says_so(repo: StageRepo) -> None:
    probe = _probe(repo, "Call `brand_new_function`.")

    assert "No commit in the history added or removed its text." in probe.text


def test_a_command_a_name_with_a_slash_and_a_version_are_no_cited_items(repo: StageRepo) -> None:
    body = "Run `git log -S x -- a/b`, see `owner/repo` and release 0.41."

    probe = _probe(repo, body)

    assert (probe.text, probe.missing, probe.skipped) == ("", (), ())


def test_the_probe_stops_at_the_bound_and_lists_the_items_it_skipped(repo: StageRepo) -> None:
    names = {f"src/devops_cli/f{i}.py": "x = 1\n" for i in range(12)}
    repo.track(names)
    body = " ".join(f"`{name}`" for name in names)

    probe = _probe(repo, body)

    bound = CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS
    assert (bound < len(names), probe.commands) == (True, bound)
    assert probe.skipped == tuple(list(names)[bound:])
    assert f"Not probed, the bound of {bound} commands is reached:" in probe.text


def test_a_missing_item_that_the_bound_cuts_off_from_its_removal_probe_is_listed(
    repo: StageRepo,
) -> None:
    names = [f"src/devops_cli/m{i}.py" for i in range(6)]
    body = " ".join(f"`{name}`" for name in names)

    probe = _probe(repo, body)

    assert probe.commands == 10
    assert probe.missing == tuple(names[:5])
    assert probe.skipped == (names[5],)


def test_every_command_reads_and_the_checkout_does_not_change(
    repo: StageRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[tuple[str, ...]] = []

    def spy(checkout: Path, *args: str) -> tuple[int, str]:
        ran.append(args)
        return git_result(checkout, *args)

    monkeypatch.setattr(stage_probe, "git_result", spy)
    body = f"`{LIVE}` `{GONE}` `keep_comment` `validate_url`"

    _probe(repo, body)

    assert {args[0] for args in ran} == {"cat-file", "grep", "log", "ls-tree"}
    assert repo.git("status", "--porcelain") == ""


def test_missing_path_an_open_plan_creates_is_a_dependency(repo: StageRepo) -> None:
    probe = _probe(repo, f"Add `{GONE}` and change `{LIVE}`.")

    assert probe.missing == (GONE,)
    assert blocked_by(probe.missing, {GONE: 3308, LIVE: 3309}) == (3308,)
    assert blocked_by(probe.missing, {LIVE: 3309}) == ()


def test_a_cited_class_field_names_its_file_and_line(repo: StageRepo) -> None:
    repo.track({MODEL: MODEL_SOURCE})

    probe = _probe(repo, "The model `PullStatus.labels` holds the labels.")

    assert f"`PullStatus` defines the field `labels` at {MODEL}:2" in probe.text
    assert probe.missing == ()
    assert "The path `PullStatus.labels`" not in probe.text


def test_a_cited_class_field_that_the_class_lacks_is_missing(repo: StageRepo) -> None:
    repo.track({MODEL: MODEL_SOURCE})

    probe = _probe(repo, "The model `PullStatus.unknown_field` holds the value.")

    assert f"`PullStatus` defines no field `unknown_field` in `{MODEL}`." in probe.text
    assert probe.missing == ("PullStatus.unknown_field",)
    assert "The path `PullStatus.unknown_field`" not in probe.text


def test_a_dotted_reference_that_names_no_class_stays_a_path(repo: StageRepo) -> None:
    probe = _probe(repo, "Change `README.unknown`.")

    assert "The path `README.unknown` is no file of the staging commit." in probe.text
    assert probe.missing == ("README.unknown",)


def test_a_dotted_absence_statement_is_a_false_premise(repo: StageRepo) -> None:
    repo.track({MODEL: MODEL_SOURCE})

    probe = _probe(repo, "The issue says `PullStatus.labels` is absent.")

    assert probe.missing == ()
    assert probe.false_premises == (f"`PullStatus` defines the field `labels` at {MODEL}:2",)


def test_a_split_absence_statement_is_a_false_premise(repo: StageRepo) -> None:
    repo.track({MODEL: MODEL_SOURCE})

    probe = _probe(repo, "The issue says `PullStatus` defines no `labels`.")

    assert probe.false_premises == (f"`PullStatus` defines the field `labels` at {MODEL}:2",)


def test_a_true_absence_statement_is_no_false_premise(repo: StageRepo) -> None:
    repo.track({MODEL: MODEL_SOURCE})

    probe = _probe(repo, "The issue says `PullStatus` has no `closed_at`.")

    assert probe.false_premises == ()
    assert "PullStatus.closed_at" in probe.missing


def test_the_field_probe_counts_its_commands_and_leaves_the_checkout(
    repo: StageRepo,
) -> None:
    repo.track({MODEL: MODEL_SOURCE})

    probe = _probe(repo, "`PullStatus.labels` and `PullStatus.state`.")

    assert probe.commands == 2
    assert repo.git("status", "--porcelain") == ""


PUBLISH = "src/devops_cli/publish.py"
# The call site of #3368: `_publish` calls the helper, and the helper runs the title check.
PUBLISH_SOURCE = (
    "def _publish():\n"
    "    title = self._delivery_title()\n"
    "\n"
    "\n"
    "def _delivery_title(self):\n"
    "    if not title_problems(title, declared):\n"
    "        raise Stop()\n"
)
PUBLISH_WITHOUT_CHECK = (
    "def _publish():\n"
    "    title = self._delivery_title()\n"
    "\n"
    "\n"
    "def _delivery_title(self):\n"
    "    return title\n"
)
TITLES = "src/devops_cli/titles.py"
TITLES_SOURCE = "def delivery_title(title):\n    return title_problems(title, ())\n"
CLAIM = "The plan says that `_publish` runs no `title_problems` check."


def test_a_check_in_a_helper_body_of_the_call_site_is_found(repo: StageRepo) -> None:
    repo.track({PUBLISH: PUBLISH_SOURCE})
    sha = repo.git("rev-parse", "HEAD")

    claims = claimed_missing_checks((CLAIM,))
    probe = check_claims(repo.clone, sha, claims, CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS)

    assert claims == (("_publish", "title_problems"),)
    assert probe.false_premises == (
        f"`title_problems` is called at {PUBLISH}:6, so the plan claim that `_publish` runs no "
        "such check is false.",
    )
    assert (probe.commands, probe.left) == (2, CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS - 2)
    assert probe.skipped == ()
    assert repo.git("status", "--porcelain") == ""


def test_a_check_in_the_body_of_the_call_site_is_found(repo: StageRepo) -> None:
    repo.track({PUBLISH: PUBLISH_SOURCE})
    sha = repo.git("rev-parse", "HEAD")

    probe = check_claims(
        repo.clone,
        sha,
        (("_delivery_title", "title_problems"),),
        CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS,
    )

    assert probe.false_premises == (
        f"`title_problems` is called at {PUBLISH}:6, so the plan claim that `_delivery_title` "
        "runs no such check is false.",
    )


def test_a_check_that_only_another_file_holds_names_its_path_and_line(repo: StageRepo) -> None:
    repo.track({PUBLISH: PUBLISH_WITHOUT_CHECK, TITLES: TITLES_SOURCE})
    sha = repo.git("rev-parse", "HEAD")

    probe = check_claims(
        repo.clone, sha, claimed_missing_checks((CLAIM,)), CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS
    )

    assert probe.false_premises == (
        f"`title_problems` is called at {TITLES}:2, so the plan claim that `_publish` runs no "
        "such check is false.",
    )
    assert probe.skipped == ()


def test_a_call_site_that_is_no_python_source_leaves_the_search_to_the_tree(
    repo: StageRepo,
) -> None:
    rust = "src/devops_cli/publish.rs"
    repo.track({rust: "fn _publish() {\n    let title = 1;\n}\n", TITLES: TITLES_SOURCE})
    sha = repo.git("rev-parse", "HEAD")

    probe = check_claims(
        repo.clone, sha, (("_publish", "title_problems"),), CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS
    )

    assert probe.false_premises == (
        f"`title_problems` is called at {TITLES}:2, so the plan claim that `_publish` runs no "
        "such check is false.",
    )


def test_a_claim_with_no_call_site_adds_no_line(repo: StageRepo) -> None:
    general = "The plan says that the title check is missing, and adds it."
    named = "The plan says that the `title_problems` check is missing."

    assert claimed_missing_checks((general, named)) == ()
    probe = check_claims(
        repo.clone, repo.git("rev-parse", "HEAD"), (), CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS
    )

    assert (probe.false_premises, probe.commands) == ((), 0)
    assert _probe(repo, general).left == CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS


def test_a_claim_with_no_command_left_is_skipped(
    repo: StageRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo.track({PUBLISH: PUBLISH_SOURCE})
    ran: list[tuple[str, ...]] = []

    def spy(checkout: Path, *args: str) -> tuple[int, str]:
        ran.append(args)
        return git_result(checkout, *args)

    monkeypatch.setattr(stage_probe, "git_result", spy)

    probe = check_claims(
        repo.clone, repo.git("rev-parse", "HEAD"), claimed_missing_checks((CLAIM,)), 0
    )

    assert (probe.skipped, probe.false_premises, probe.commands, probe.left) == (
        ("title_problems",),
        (),
        0,
        0,
    )
    assert ran == []
