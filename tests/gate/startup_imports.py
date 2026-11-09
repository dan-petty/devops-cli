"""The startup-import budget: the `startup-imports` row of `devops ci` (#1687, #858, #2164).

The start of the CLI must not import a heavy package, and the help of a command must stay within
a count of modules. Each probe starts one fresh interpreter, because a module that one argv
imports stays in `sys.modules` and would hide the import of the next. The probes of the help
run under `-X importtime`, which gives the count of imports and the slowest of them. A failure
names the ten slowest imports.

The row measures the process of each probe, so it runs outside pytest: a pytest worker that runs
56 probes holds one core for minutes (#2369).
"""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from typing import Final

from devops_cli.main import _COMMAND_SPECS
from tests.support.paths import REPO_ROOT

CONST_CLI_HEAVY_MODULES: tuple[str, ...] = (
    "pydantic_ai",
    "kubernetes",
    "docker",
    "fastmcp",
    "qdrant_client",
    "google.genai",
    "anthropic",
    "openai",
    "agentops",
    "litellm",
    "libtmux",
    "textual",
)
DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION: int = 550
DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION: int = 75
DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP: int = 1100
DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP: int = 250

_PROBE_TIMEOUT_SECONDS: Final = 300
_MAX_PARALLEL_PROBES: Final = 4
_SLOWEST_COUNT: Final = 10

# Each argv below runs once, in a fresh interpreter of its own, and every check on that argv reads
# that one run: separate interpreters keep one command's imports out of another's count, and one
# run per argv keeps two checks from measuring the same start twice.
_STARTUP_PROBE = """
import sys
import devops_cli.entry

try:
    devops_cli.entry.main(sys.argv[1:])
except SystemExit:
    pass
print("\\n__MODULES__", *sys.modules)
"""


@dataclass(frozen=True)
class StartupImports:
    """What one fresh interpreter running `devops <argv>` imported."""

    loaded: frozenset[str]
    """Every name in `sys.modules` once the command returned."""
    imported: frozenset[str]
    """Every module `-X importtime` reported, failed imports included: what the budgets count."""
    slowest: tuple[tuple[str, float], ...]
    """The ten slowest imports by cumulative seconds, a diagnostic only."""

    @property
    def devops_modules(self) -> frozenset[str]:
        """The devops_cli modules among those imported."""
        return frozenset(m for m in self.imported if m.startswith("devops_cli"))

    def found(self, modules: tuple[str, ...]) -> list[str]:
        """Return those of `modules` the run loaded or tried to import."""
        return [m for m in modules if m in self.loaded or m in self.imported]

    def report(self) -> str:
        """Describe the counts and the slowest imports for a failure message."""
        slowest = "\n".join(f"  {mod}: {sec:.4f}s" for mod, sec in self.slowest)
        return (
            f"{len(self.imported)} modules, {len(self.devops_modules)} devops_cli modules. "
            f"Slowest imports:\n{slowest}"
        )


@dataclass(frozen=True)
class ImportBudget:
    """A structural startup budget (#1687): how many modules, and devops_cli modules, a start imports."""

    name: str
    total: int
    devops: int

    def admits(self, probe: StartupImports) -> bool:
        """Return whether the run stayed within both counts."""
        return len(probe.imported) <= self.total and len(probe.devops_modules) <= self.devops


MAIN_AND_VERSION_BUDGET = ImportBudget(
    "main and version",
    DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
    DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION,
)
COMMAND_HELP_BUDGET = ImportBudget(
    "command help",
    DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP,
    DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP,
)

# The budgets an argv holds besides the heavy-module check every help argv holds.
BUDGETS_BY_ARGV: dict[tuple[str, ...], tuple[ImportBudget, ...]] = {
    ("--version",): (MAIN_AND_VERSION_BUDGET,),
    ("--help",): (MAIN_AND_VERSION_BUDGET, COMMAND_HELP_BUDGET),
    ("ai", "--help"): (COMMAND_HELP_BUDGET,),
    ("ai", "benchmark", "--help"): (COMMAND_HELP_BUDGET,),
    ("review", "--help"): (COMMAND_HELP_BUDGET,),
    ("k8s", "--help"): (COMMAND_HELP_BUDGET,),
}

# The argvs that also import no telemetry and no pydantic_ai (#858).
TELEMETRY_FREE_ARGVS: frozenset[tuple[str, ...]] = frozenset(
    {("--help",), ("ci", "--help"), ("workspace", "--help")}
)
TELEMETRY_MODULES = ("logfire", "opentelemetry.sdk", "pydantic_ai")

_DRY_RUN_PLANS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("ai", "benchmark", "--dry-run"), CONST_CLI_HEAVY_MODULES),
    (("k8s", "deploy-stack", "--dry-run"), CONST_CLI_HEAVY_MODULES),
    (("review", "path", "README.md", "--dry-run"), ("kubernetes", "docker", "qdrant_client")),
)


def help_argvs() -> list[tuple[str, ...]]:
    """`--version`, the root `--help`, every command group's `--help`, and every argv the tables name."""
    return sorted(
        {
            ("--version",),
            ("--help",),
            *((cmd, "--help") for cmd in _COMMAND_SPECS),
            *BUDGETS_BY_ARGV,
            *TELEMETRY_FREE_ARGVS,
        }
    )


def parse_importtime_line(line: str) -> tuple[str, float] | None:
    """Read one line of `-X importtime` as (module, cumulative seconds), or None for another line."""
    if not line.strip().startswith("import time:"):
        return None
    parts = line.split("|")
    if len(parts) != 3:
        return None
    s_str = parts[0].replace("import time:", "").strip()
    if not s_str.isdigit():
        return None
    return parts[2].strip(), int(parts[1].strip()) / 1_000_000


def parse_importtime(stderr: str) -> dict[str, float]:
    """Map each module `-X importtime` reported to its largest cumulative import time in seconds."""
    cumulative: dict[str, float] = {}
    for parsed in map(parse_importtime_line, stderr.splitlines()):
        if parsed is not None:
            mod, seconds = parsed
            cumulative[mod] = max(seconds, cumulative.get(mod, 0.0))
    return cumulative


def read_startup_imports(stdout: str, stderr: str) -> StartupImports:
    """Read the output of a run of `_STARTUP_PROBE` under `-X importtime`."""
    modules_line = next(line for line in stdout.splitlines() if line.startswith("__MODULES__"))
    cumulative = parse_importtime(stderr)
    slowest = sorted(cumulative.items(), key=lambda item: item[1], reverse=True)[:_SLOWEST_COUNT]
    return StartupImports(
        loaded=frozenset(modules_line.split()[1:]),
        imported=frozenset(cumulative),
        slowest=tuple(slowest),
    )


def clean_env(extra: Mapping[str, str] | None = None, drop: tuple[str, ...] = ()) -> dict[str, str]:
    """The environment of a probe: no telemetry and no plugin override, `src` on PYTHONPATH."""
    env = dict(os.environ)
    for name in ("PYDANTIC_DISABLE_PLUGINS", "LOGFIRE_TOKEN", *drop):
        env.pop(name, None)
    for name in list(env):
        if name.startswith("DEVOPS_CLI_TELEMETRY__"):
            env.pop(name, None)
    src_dir = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{src_dir}:{existing}" if existing else src_dir
    env.update(extra or {})
    return env


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run one probe in a fresh interpreter; a probe that exits non-zero raises."""
    return subprocess.run(
        [sys.executable, *args],
        env=env,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=_PROBE_TIMEOUT_SECONDS,
    )


def probe_startup_imports(argv: tuple[str, ...], preamble: str = "") -> StartupImports:
    """Run `devops <argv>` in a fresh interpreter under `-X importtime` and record its imports.

    The interpreter imports `devops_cli.entry` and calls its `main`, as the `devops` script does.
    `preamble` runs first in the same interpreter, for the control that imports a heavy package.
    """
    done = _run(["-X", "importtime", "-c", preamble + _STARTUP_PROBE, *argv], clean_env())
    return read_startup_imports(done.stdout, done.stderr)


def help_problems(argv: tuple[str, ...], probe: StartupImports) -> list[str]:
    """Name what one help argv breaks: a heavy module, a telemetry module or a budget."""
    heavy = probe.found(CONST_CLI_HEAVY_MODULES)
    telemetry = (
        [m for m in TELEMETRY_MODULES if m in probe.loaded] if argv in TELEMETRY_FREE_ARGVS else []
    )
    breached = [b.name for b in BUDGETS_BY_ARGV.get(argv, ()) if not b.admits(probe)]
    if not (heavy or telemetry or breached):
        return []
    return [
        f"devops {' '.join(argv)}: heavy modules {heavy}, telemetry modules {telemetry}, "
        f"budgets breached {breached}. {probe.report()}"
    ]


def control_problems(probe: StartupImports) -> list[str]:
    """The control: a run that imports a heavy package must fail the budget (#1687)."""
    caught = (
        "pydantic_ai" in probe.found(CONST_CLI_HEAVY_MODULES),
        len(probe.imported) > DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION,
    )
    if caught == (True, True):
        return []
    return [f"the control passed: a run that imports pydantic_ai was not caught ({caught})"]


def dry_run_problems(
    argv: tuple[str, ...], forbidden: tuple[str, ...], probe: StartupImports
) -> list[str]:
    """A `--dry-run` imports only what its plan needs."""
    loaded = [m for m in forbidden if m in probe.loaded]
    return [f"devops {' '.join(argv)}: imported {loaded}"] if loaded else []


@dataclass(frozen=True)
class ScriptProbe:
    """A probe that runs its own code in a fresh interpreter and prints one marked line."""

    name: str
    code: str
    expected: object
    """What the JSON value after the marker must equal."""
    marker: str
    extra_env: Mapping[str, str] = field(default_factory=dict)
    drop_env: tuple[str, ...] = ()


def _json_after(stdout: str, marker: str) -> object:
    """Read the JSON text that follows the marker on its line."""
    line = next(line for line in stdout.splitlines() if line.startswith(marker))
    return json.loads(line.removeprefix(marker))


_GITHUB_HELP_ARGVS = [["--help"], ["gh", "--help"], ["roadmap", "--help"], ["pr", "--help"]]

SCRIPT_PROBES: tuple[ScriptProbe, ...] = (
    ScriptProbe(
        "PYDANTIC_DISABLE_PLUGINS merges logfire-plugin with the plugins of the caller",
        """
import json
import os
import devops_cli.entry

try:
    devops_cli.entry.main(["--help"])
except SystemExit:
    pass

plugins = [p.strip() for p in os.environ.get("PYDANTIC_DISABLE_PLUGINS", "").split(",")]
print("__R__" + json.dumps(["some-other-plugin" in plugins, "logfire-plugin" in plugins]))
""",
        [True, True],
        "__R__",
        extra_env={"PYDANTIC_DISABLE_PLUGINS": "some-other-plugin"},
    ),
    ScriptProbe(
        "no logfire plugin loads into pydantic when telemetry is enabled",
        """
import json
import devops_cli.entry

try:
    devops_cli.entry.main(["--help"])
except SystemExit:
    pass

import pydantic.plugin._loader as loader
plugins = [getattr(p, "__name__", str(p)).lower() for p in loader.get_plugins()]
print("__R__" + json.dumps(any("logfire" in p for p in plugins)))
""",
        False,
        "__R__",
        extra_env={"DEVOPS_CLI_TELEMETRY__LOGFIRE": "true"},
    ),
    ScriptProbe(
        "ai.client.factory and ai.providers import neither anthropic, google.genai nor openai",
        """
import json
import sys

import devops_cli.ai.client.factory
import devops_cli.ai.providers

print("__R__" + json.dumps([m in sys.modules for m in ("anthropic", "google.genai", "openai")]))
""",
        [False, False, False],
        "__R__",
    ),
    ScriptProbe(
        "the help leaves the ETag store of the GitHub session (cachetools) unloaded",
        f"""
import json
import sys
import devops_cli.entry

for argv in {_GITHUB_HELP_ARGVS!r}:
    try:
        devops_cli.entry.main(argv)
    except SystemExit:
        pass

print("__R__" + json.dumps("cachetools" in sys.modules))
""",
        False,
        "__R__",
    ),
    ScriptProbe(
        "main, commands.ci, the tracer and http load no heavy module",
        f"""
import json
import sys

import devops_cli.main
import devops_cli.commands.ci
from devops_cli.telemetry.tracer import get_tracer
get_tracer()
import devops_cli.http

print("__R__" + json.dumps([m for m in {CONST_CLI_HEAVY_MODULES!r} if m in sys.modules]))
""",
        [],
        "__R__",
    ),
    ScriptProbe(
        "core.validation and http.egress do not import pydantic_ai",
        """
import json
import sys

import devops_cli.core.validation
import devops_cli.http.egress

print("__R__" + json.dumps("pydantic_ai" in sys.modules))
""",
        False,
        "__R__",
    ),
    ScriptProbe(
        "exceptions.ai imports pydantic_ai on the first use of ModelRetry",
        """
import json
import sys

import devops_cli.exceptions.ai

before = "pydantic_ai" in sys.modules
_ = devops_cli.exceptions.ai.ModelRetry
print("__R__" + json.dumps([before, "pydantic_ai" in sys.modules]))
""",
        [False, True],
        "__R__",
    ),
    ScriptProbe(
        "the entry point turns off the pydantic-ai banner (#2398)",
        """
import json
import os
import devops_cli.entry

print("__R__" + json.dumps(os.environ.get("PYDANTIC_AI_NO_BANNER", "")))
""",
        "1",
        "__R__",
        drop_env=("PYDANTIC_AI_NO_BANNER",),
    ),
)


def script_problems(probe: ScriptProbe, stdout: str) -> list[str]:
    """Name a script probe whose marked value differs from the expected one."""
    found = _json_after(stdout, probe.marker)
    return (
        [] if found == probe.expected else [f"{probe.name}: got {found!r}, not {probe.expected!r}"]
    )


def _help_probe(argv: tuple[str, ...]) -> list[str]:
    """Run one help argv and return what it breaks."""
    return help_problems(argv, probe_startup_imports(argv))


def _control_probe() -> list[str]:
    """Run the control: the root help after an import of a heavy package."""
    return control_problems(probe_startup_imports(("--help",), "import pydantic_ai\n"))


def _dry_run_probe(argv: tuple[str, ...], forbidden: tuple[str, ...]) -> list[str]:
    """Run one `--dry-run` argv and return the forbidden modules it imports."""
    return dry_run_problems(argv, forbidden, probe_startup_imports(argv))


def _script_probe(probe: ScriptProbe) -> list[str]:
    """Run the code of a script probe and compare its marked value."""
    done = _run(["-c", probe.code], clean_env(probe.extra_env, probe.drop_env))
    return script_problems(probe, done.stdout)


def _all_probes() -> list[tuple[str, Callable[[], list[str]]]]:
    """Every probe of the row as a name and a function that runs it and returns its problems."""
    return [
        *((f"help {argv}", partial(_help_probe, argv)) for argv in help_argvs()),
        ("control", _control_probe),
        *(
            (f"dry-run {argv}", partial(_dry_run_probe, argv, forbidden))
            for argv, forbidden in _DRY_RUN_PLANS
        ),
        *((script.name, partial(_script_probe, script)) for script in SCRIPT_PROBES),
    ]


def problems() -> list[str]:
    """Run every probe, a few at a time, and return what they break."""
    probes = _all_probes()
    workers = min(os.process_cpu_count() or 1, _MAX_PARALLEL_PROBES)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [(name, pool.submit(run)) for name, run in probes]
        found: list[str] = []
        for name, future in futures:
            try:
                found.extend(future.result())
            except subprocess.CalledProcessError as exc:
                found.append(f"{name}: exit {exc.returncode}: {exc.stderr[-400:]}")
    return found


def main(argv: list[str] | None = None) -> int:
    """Print each problem and the CPU time of the probes, and return 1 when there is a problem."""
    found = problems()
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    print(
        f"startup imports: {len(_all_probes())} probes, "
        f"{children.ru_utime + children.ru_stime:.1f} s of CPU time "
        f"({children.ru_utime:.1f} s user, {children.ru_stime:.1f} s system)"
    )
    for line in found:
        print(f"startup imports: {line}", file=sys.stderr)
    return 1 if found else 0
