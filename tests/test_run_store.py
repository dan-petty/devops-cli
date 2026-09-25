"""The evaluation run store: every benchmark and evaluation kept and shared (#554).

Only some mechanisms kept their results, each in its own shape, and none were shared between
workstations. Each run is now one record in the data directory, mirrored to a shared Valkey
index that can be rebuilt from the files, and every mechanism works without Valkey.
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai import run_store
from devops_cli.ai.gateway_tune import DeploymentTune, GpuInfo, TuneReport
from devops_cli.ai.review import runner
from devops_cli.ai.review.profile import ReviewProfile, StageProfile, report_profile
from devops_cli.ai.run_store import (
    INDEX_PREFIX,
    Mechanism,
    RunIndex,
    load_runs,
    new_run,
    record_run,
    save_run,
    share_runs,
)
from devops_cli.commands import ai_gateway
from devops_cli.commands import review as review_commands
from devops_cli.config import settings as settings_module
from devops_cli.config.settings import (
    get_runs_index_password,
    load_settings,
    reset_settings_cache,
    save_settings,
)
from devops_cli.k8s import node_port
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})


class FakeValkey:
    """The Valkey commands the index uses, kept in memory."""

    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}
        self.round_trips = 0
        self.host, self.port, self.closed = "index.example", 6379, False

    def _run(self, name: str, *args: Any) -> Any:
        if name == "SET":
            self.strings[args[0]] = args[1]
            return "OK"
        if name == "ZADD":
            self.sorted_sets.setdefault(args[0], {})[args[2]] = float(args[1])
            return 1
        if name == "ZRANGE":
            members = self.sorted_sets.get(args[0], {})
            return sorted(members, key=lambda m: (members[m], m))
        raise AssertionError(f"unexpected command {name}")

    def pipeline(self, commands: list[list[Any]]) -> list[Any]:
        self.round_trips += 1
        return [self._run(*command) for command in commands]

    def execute(self, *parts: Any) -> Any:
        self.round_trips += 1
        return self._run(*parts)

    def get(self, key: str) -> str | None:
        return self.strings.get(key)

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def valkey(monkeypatch: pytest.MonkeyPatch) -> FakeValkey:
    """A reachable run index."""
    fake = FakeValkey()
    monkeypatch.setattr(RunIndex, "from_settings", classmethod(lambda cls: cls(fake)))  # type: ignore[arg-type]
    return fake


def test_a_record_names_its_setup_and_subject_by_content() -> None:
    """Verify equal setups and subjects share a digest whatever their key order, and the record
    carries the devops-cli version and the checkout's commit."""
    from devops_cli import __version__

    a = new_run(Mechanism.PROMPT_EVAL, setup={"a": 1, "b": [2]}, subject={"x": 1}, results={})
    b = new_run(Mechanism.PROMPT_EVAL, setup={"b": [2], "a": 1}, subject={"x": 2}, results={})

    assert (
        a.fingerprint == b.fingerprint,
        a.subject_key == b.subject_key,
        a.run_id == b.run_id,
        a.version,
        (a.commit or "").split("-")[0].isalnum(),
    ) == (True, False, False, __version__, True)


def test_records_are_kept_by_mechanism_and_read_back_oldest_first(tmp_path: Path) -> None:
    """Verify records round-trip through the data directory, by mechanism, skipping unreadable
    files."""
    first = new_run(Mechanism.CORPUS_SCORE, setup={}, subject={}, results={"recall": 0.5})
    second = new_run(Mechanism.CORPUS_SCORE, setup={}, subject={}, results={"recall": 0.7})
    other = new_run(Mechanism.GATEWAY_TUNE, setup={}, subject={}, results={})
    paths = [save_run(r, tmp_path) for r in (second, first, other)]
    (tmp_path / "corpus-score" / "broken.json").write_text("{", encoding="utf-8")

    assert (
        [p.relative_to(tmp_path).parts[0] for p in paths],
        [r.results for r in load_runs(Mechanism.CORPUS_SCORE, tmp_path)],
        len(load_runs(root=tmp_path)),
    ) == (
        ["corpus-score", "corpus-score", "gateway-tune"],
        [{"recall": 0.5}, {"recall": 0.7}],
        3,
    )


def test_the_index_holds_each_record_by_mechanism_and_subject(valkey: FakeValkey) -> None:
    """Verify a record is shared in one round trip, and found by mechanism, subject and id."""
    record = new_run(Mechanism.REVIEW_BENCHMARK, setup={}, subject={"corpus": "c"}, results={})

    shared = share_runs(record)
    with RunIndex(valkey) as index:  # type: ignore[arg-type]
        found = index.get(Mechanism.REVIEW_BENCHMARK, record.run_id)
        ids = index.run_ids(Mechanism.REVIEW_BENCHMARK)
    subject_key = f"{INDEX_PREFIX}:subject:review-benchmark:{record.subject_key}"

    assert (shared, found, ids, list(valkey.sorted_sets[subject_key]), valkey.closed) == (
        (True, "index.example:6379"),
        record,
        [record.run_id],
        [record.run_id],
        True,
    )


def test_runs_are_kept_locally_when_no_index_is_configured_or_reachable() -> None:
    """Verify a run is kept in the data directory and says why it was not shared."""
    unconfigured = record_run(Mechanism.PROMPT_EVAL, setup={}, subject={}, results={})
    settings = load_settings()
    settings.runs.index_url = "valkey://127.0.0.1:9"
    save_settings(settings)
    unreachable = record_run(Mechanism.PROMPT_EVAL, setup={}, subject={}, results={})

    assert (
        (unconfigured.shared, "devops ai runs connect" in unconfigured.detail),
        (unreachable.shared, "devops ai runs reindex" in unreachable.detail),
        len(load_runs(Mechanism.PROMPT_EVAL)),
    ) == ((False, True), (False, True), 2)


def test_reindex_rebuilds_the_index_from_the_data_directory(valkey: FakeValkey) -> None:
    """Verify every recorded run reaches the index in one round trip."""
    for mechanism in (Mechanism.CORPUS_SCORE, Mechanism.GATEWAY_TUNE):
        save_run(new_run(mechanism, setup={}, subject={}, results={}))

    result = cli.invoke(app, ["ai", "runs", "reindex"])

    assert (result.exit_code, len(valkey.strings), valkey.round_trips) == (0, 2, 1)


def test_reindex_without_an_index_fails_and_says_how_to_connect() -> None:
    """Verify reindexing with no index configured exits non-zero, naming the command to run."""
    save_run(new_run(Mechanism.CORPUS_SCORE, setup={}, subject={}, results={}))

    result = cli.invoke(app, ["ai", "runs", "reindex"])

    assert (result.exit_code, "devops ai runs connect" in result.output) == (1, True)


def _fake_cluster(calls: list[list[str]]) -> Any:
    service = {
        "spec": {"type": "NodePort", "ports": [{"name": "valkey", "port": 6379, "nodePort": 31379}]}
    }
    password = base64.b64encode(b"s3cret").decode()

    def run(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if "service" in cmd:
            out = json.dumps(service)
        elif "secret" in cmd:
            out = password
        else:
            out = "https://cluster.example:6443"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    return run


def test_connect_finds_the_index_saves_it_and_indexes_local_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify connect reads the NodePort and password from the cluster, stores the password in
    the keyring rather than the config file, and indexes the runs already kept."""
    calls: list[list[str]] = []
    fake = FakeValkey()
    connected: list[tuple[str, str | None]] = []

    def connect(cls: type[RunIndex], url: str, password: str | None) -> RunIndex:
        connected.append((url, password))
        return cls(fake)  # type: ignore[arg-type]

    monkeypatch.setattr(node_port, "run_subprocess", _fake_cluster(calls))
    monkeypatch.setattr(RunIndex, "connect", classmethod(connect))
    # Secrets go to an in-memory store, never a keyring the test machine may hold.
    monkeypatch.setenv("DEVOPS_CLI_HEADLESS_AUTH", "true")
    monkeypatch.setattr(settings_module, "_EPHEMERAL_CI_SECRETS", {})
    save_run(new_run(Mechanism.GATEWAY_TUNE, setup={}, subject={}, results={}))

    result = cli.invoke(app, ["ai", "runs", "connect"])
    reset_settings_cache()
    settings = load_settings()

    assert (
        result.exit_code,
        connected,
        settings.runs.index_url,
        get_runs_index_password(settings),
        "s3cret" in settings.model_dump_json() + result.output,
        len(fake.strings),
    ) == (
        0,
        [("valkey://cluster.example:31379", "s3cret")],
        "valkey://cluster.example:31379",
        "s3cret",
        False,
        1,
    )


def test_a_review_benchmark_is_kept_with_its_setup_and_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a benchmark's record carries its personas and page size, and names its corpus by
    content."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "site.yaml").write_text("- hosts: all\n", encoding="utf-8")

    def fake_review(**_: Any) -> None:
        report_profile(
            ReviewProfile(
                session_id="s",
                target=str(corpus),
                total_wall_seconds=10,
                stages=[StageProfile(name="persona_review", wall_seconds=5)],
            )
        )

    monkeypatch.setattr(review_commands, "path", fake_review)
    monkeypatch.setattr(runner, "_get_reviews_base_dir", lambda: tmp_path / "reviews")

    result = cli.invoke(app, ["review", "benchmark", str(corpus), "-n", "1", "--all"])
    (record,) = load_runs(Mechanism.REVIEW_BENCHMARK)

    assert (
        result.exit_code,
        (record.setup["all_personas"], record.setup["page_chars"] > 0),
        record.subject == {"corpus_digest": record.results["corpus_digest"], "target": "corpus"},
        "Kept on this workstation only" in result.output,
    ) == (0, (True, True), True, True)


def test_prompt_evaluations_are_kept_and_json_output_stays_parseable(tmp_path: Path) -> None:
    """Verify a prompt evaluation is kept by dataset content, announcing on stderr under --json."""
    dataset = tmp_path / "feedback.jsonl"
    record = {"title": "A finding", "status": "VERIFIED", "location": "src/app.py:1"}
    dataset.write_text(json.dumps(record | {"persona": "devsecops"}) + "\n", encoding="utf-8")

    result = cli.invoke(app, ["ai", "prompt-eval", "--json", "--dataset", str(dataset)])
    (kept,) = load_runs(Mechanism.PROMPT_EVAL)

    assert (
        result.exit_code,
        json.loads(result.stdout)["dataset_digest"] == kept.subject["dataset_digest"],
        "Saved prompt-eval run" in result.stderr,
    ) == (0, True, True)


def test_a_gateway_tune_is_kept_with_its_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a tune's record names each deployment's backend, weight and GPUs as its setup."""
    report = TuneReport(
        model_group="devops-review",
        prompt_tokens=4096,
        max_tokens=64,
        deployments=[
            DeploymentTune(
                deployment_id="d1",
                backend="vllm",
                model="hosted_vllm/qwen",
                api_base="http://vllm.example:8000/v1",
                current_weight=5,
                engine="vllm",
                gpus=[GpuInfo(name="RTX 3090", memory_mib=24576)],
            )
        ],
    )
    monkeypatch.setattr(ai_gateway, "tune_pool", lambda **_: report)
    monkeypatch.setattr(ai_gateway, "resolve_context", lambda context: None)

    result = cli.invoke(app, ["ai", "gateway", "tune", "--format", "json"])
    (kept,) = load_runs(Mechanism.GATEWAY_TUNE)

    assert (
        result.exit_code,
        json.loads(result.stdout)["model_group"],
        kept.subject,
        kept.setup["pool"],
    ) == (
        0,
        "devops-review",
        {"model_group": "devops-review"},
        [
            {
                "backend": "vllm",
                "model": "hosted_vllm/qwen",
                "weight": 5,
                "engine": "vllm",
                "gpus": ["RTX 3090"],
            }
        ],
    )


def test_ai_benchmarks_are_kept_and_dry_runs_are_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a task benchmark is kept with its models and tasks, and a dry run measures nothing
    worth keeping."""
    from devops_cli.ai.benchmark.runner import BenchmarkRunner
    from devops_cli.models.benchmark import BenchmarkReport

    args = ["ai", "benchmark", "--models", "m2,m1", "--tasks", "security", "--format", "json"]
    dry = cli.invoke(app, [*args, "--dry-run"])
    monkeypatch.setattr(
        BenchmarkRunner,
        "execute",
        lambda self: BenchmarkReport(
            session_id="b", models_evaluated=self.models, tasks_run=self.tasks
        ),
    )
    real = cli.invoke(app, args)
    (kept,) = load_runs(Mechanism.AI_BENCHMARK)

    assert (
        (dry.exit_code, real.exit_code),
        kept.setup["models"],
        kept.subject["kind"],
        len(kept.subject["tasks"]) > 0,
    ) == ((0, 0), ["m1", "m2"], "tasks", True)


def test_an_installed_package_reports_no_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a package outside a devops-cli checkout, such as one in a project's virtual
    environment, does not claim that project's commit."""
    package = tmp_path / "site-packages" / "devops_cli" / "ai"
    package.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    monkeypatch.setattr(run_store, "__file__", str(package / "run_store.py"))

    assert run_store.source_commit() is None
