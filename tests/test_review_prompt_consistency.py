"""The review prompts agree with each other and with what the pipeline loads (#951).

In review session `20261001-224227`, 87% of the 563 reported findings were false. An audit of
every prompt the pipeline sends tied each recurring failure to the text that invited it: one
prompt asking for what another calls a non-defect, an instruction to name CVE IDs, examples
that anchored `HIGH` and `0.95`, prompt files nothing loads, and a reply schema of fields the
pipeline owns. These tests pin the prompts against each of those.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import sys
import textwrap
import tokenize
from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.ai.agents.pydantic_agent import PydanticAgent
from devops_cli.ai.mcp.server import code_review_prompt
from devops_cli.ai.personas import PERSONAS, Persona
from devops_cli.ai.review.classification import FileContextType, build_context_review_prompt
from devops_cli.ai.review.verification import _check_placeholder_advisory_hallucination
from devops_cli.ai.review_schema import (
    Finding,
    ReviewResult,
    SavedFinding,
    _review_result_from_dict,
    parse_review_response,
)
from devops_cli.config.defaults import DEFAULT_REVIEW_CONVENTIONS_MAX_CHARS
from devops_cli.security.sanitizer import mask_secrets

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src" / "devops_cli"
_AI = _SRC / "ai"
_TASKS = _AI / "tasks"
_PERSONAS = _AI / "personas"
_VERIFIER = "tasks/verify_finding_system.md"
_MCP_OUTPUT = "tasks/mcp_code_review_output.md"

# Every prompt a reviewer model reads before it writes findings: the persona system prompt
# (role, `review.md`, the persona's own prompt, guardrails), the page prompt for each file kind,
# the output format the MCP `code_review_prompt` adds, and the prompts of the fallback persona
# loop.
_GENERATOR_PROMPTS: tuple[str, ...] = (
    "tasks/review.md",
    "tasks/code_review_prompt.md",
    _MCP_OUTPUT,
    "tasks/docs_review_prompt.md",
    "tasks/config_review_prompt.md",
    "tasks/guardrails_isolation.md",
    "tasks/review_output_instruction.md",
    "tasks/paginated_review_protocol.md",
    "tasks/path_review_prompt.md",
    "tasks/compose.md",
    *(
        f"personas/{persona.value}/{name}"
        for persona in Persona
        for name in ("role.md", "prompt.md")
    ),
)

# What `review.md` or the verifier calls a non-defect, and the one prompt that says so. Any other
# generator prompt that names it either asks for it or restates the exemption, and restated
# copies drift apart: `config_review_prompt.md` asked reviewers to flag the `http://` that
# `review.md` and the verifier call intended.
_NON_DEFECTS: tuple[tuple[str, str], ...] = (
    ("http://", "tasks/review.md"),
    ("NotImplementedError", "tasks/review.md"),
    ("<masked", "tasks/review.md"),
    ("default_factory", _VERIFIER),
    ("os.kill(pid, 0)", _VERIFIER),
)

# The decisions #951 put into the prompts, one marker each, by the prompt that must carry it.
_DECISIONS: tuple[tuple[str, str], ...] = (
    ("personas/devsecops/role.md", "Never cite a CVE or GHSA identifier from memory"),
    ("personas/devsecops/prompt.md", "**Untrusted**"),
    ("personas/devsecops/prompt.md", "model output, pull request and issue text"),
    ("personas/devsecops/prompt.md", "MCP and tool-call arguments"),
    ("personas/devsecops/prompt.md", "**Trusted**"),
    ("personas/devsecops/prompt.md", "values the code builds itself"),
    ("personas/devsecops/prompt.md", "the sink it reaches"),
    ("personas/devsecops/prompt.md", "Dependency advisories come from the scanners"),
    ("personas/devsecops/prompt.md", "**Return no finding**"),
    ("tasks/review.md", "**Trusted and untrusted input**"),
    ("tasks/review.md", "Where the conventions give no threat model"),
    ("tasks/review.md", "an untrusted input reaches code execution"),
    ("tasks/review.md", "a missing guard on trusted input that the project's conventions require"),
    ("tasks/review.md", "Report only what you can see"),
    ("tasks/review.md", "replacement code for the cited lines"),
    ("tasks/review.md", "copied exactly from the cited lines"),
    ("tasks/review.md", "imports the cited code"),
    ("tasks/review.md", '`"executable": false`'),
    ("tasks/review.md", "A requirement is not a defect"),
    ("tasks/code_review_prompt.md", "**Report What You Can See**"),
    ("tasks/code_review_prompt.md", "a test that cannot fail"),
    ("tasks/code_review_prompt.md", "corrected code for the cited lines"),
    (_MCP_OUTPUT, "Return one JSON object"),
    ("tasks/docs_review_prompt.md", "a statement the code contradicts"),
    ("tasks/docs_review_prompt.md", "a broken relative link"),
    ("tasks/docs_review_prompt.md", "Roadmaps, changelogs, task files and decision records"),
    ("tasks/config_review_prompt.md", "A setting the workload does not need is not a defect"),
    ("tasks/config_review_prompt.md", "A pinned version tag is pinned"),
    (_VERIFIER, "**Verified** needs the defective line"),
    (_VERIFIER, "the untrusted source and the sink it reaches"),
    (_VERIFIER, "**Trusted input**"),
    (_VERIFIER, "makes the claimed failure impossible"),
    (_VERIFIER, "**Unverified**"),
    (_VERIFIER, "Dependency advisories come from the scanners"),
    (_VERIFIER, "sit at a lockfile"),
    (_VERIFIER, "rests on a CVE or GHSA identifier, against a dependency or against code"),
    (_VERIFIER, "the value behind a marker is a real secret is about the source, and stands"),
)

# Security rules that tell a reviewer to require a guard or the verifier to verify a claim. Each
# names the untrusted input it is about: "verify where caller or external strings are stored
# unbounded" and "verify where path traversal checks run only on populated schema properties"
# named none, so they verified what the trusted-input rule refutes.
_SOURCE_BOUND_RULES: tuple[tuple[str, str], ...] = (
    ("tasks/review.md", "**Path containment"),
    ("tasks/review.md", "**Egress and SSRF**"),
    ("tasks/review.md", "**Error detail (CWE-209)**"),
    (_VERIFIER, "**Unbounded stores**"),
    (_VERIFIER, "**Exception detail size (CWE-209)**"),
    (_VERIFIER, "**Validation coverage**"),
)

# A rule that a test's own defect is a test that cannot fail, and the clause that keeps a real
# credential or vulnerability in a test file reportable, as section 7 of the verifier says.
_TEST_RULE = "cannot fail"
_TEST_FILE_EXCEPTION = "a real credential or a genuine vulnerability in a test file"

# An instruction to name an advisory identifier, or a rule that takes one as evidence. A model
# cannot look an identifier up, so it recalls one; the verifier cannot look it up either.
# `role.md` asked for "specific CVE IDs", `review.md` for "a real advisory identifier", and the
# verifier let a dependency claim stand on "a real, lookup-able `CVE-YYYY-NNNNN`".
_ADVISORY_ID_AS_EVIDENCE = re.compile(
    r"\bCVE[ -]?(?:IDs?|identifiers?)\b"
    r"|\b(?:real|valid|specific|published|lookup-able)\W+(?:[\w-]+\W+){0,2}?(?:CVE|GHSA|advisory)\b"
    r"|\bCVE-YYYY\b",
    re.IGNORECASE,
)

# The fields a reviewer writes. Everything else on a finding is set by the pipeline: the
# verifier, the criteria runner, consolidation, the scanners.
_REVIEWER_FINDING_FIELDS: frozenset[str] = frozenset(
    {
        "severity",
        "location",
        "title",
        "description",
        "fix",
        "references",
        "verification_criteria",
        "invalidation_criteria",
        "observed_value",
        "expected_value",
    }
)


def _read(name: str) -> str:
    return (_AI / name).read_text(encoding="utf-8")


def _line_with(name: str, marker: str) -> str:
    return next((line for line in _read(name).splitlines() if marker in line), "")


def _measurement_section() -> str:
    text = (_ROOT / "docs" / "SELF_IMPROVEMENT.md").read_text(encoding="utf-8")
    start = text.index("#### Measuring the threat-model and evidence-bar prompts (#951)")
    return text[start : text.index("\n### ", start)]


def _prompt_names() -> list[str]:
    return sorted(
        path.relative_to(_AI).as_posix()
        for directory in (_TASKS, _PERSONAS)
        for path in directory.rglob("*.md")
    )


def _literals_in_source(names: set[str]) -> set[str]:
    """The `names` that some string literal in the package's Python source equals.

    The tokenizer reads literals exactly and skips comments. Only modules that quote one of the
    names are tokenized, which keeps the scan fast.
    """
    quoted = re.compile("[\"']({})[\"']".format("|".join(map(re.escape, sorted(names)))))
    found: set[str] = set()
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if not quoted.search(text):
            continue
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        found.update(
            value
            for token in tokens
            if token.type == tokenize.STRING
            and ".md" in token.string
            and (value := ast.literal_eval(token.string)) in names
        )
    return found


def test_every_prompt_file_is_loaded_somewhere() -> None:
    """A prompt file nothing loads changes the prompt digest without reaching a model.

    Task prompts are loaded by name. Persona prompts are loaded as `role.md` and `prompt.md`
    from the directory of each `Persona`, so each persona has exactly those two files.
    """
    tasks = {path.name for path in _TASKS.glob("*.md")}
    loaded = _literals_in_source(tasks | {"role.md", "prompt.md"})
    unloaded_tasks = sorted(tasks - loaded)
    persona_files = sorted(
        path.relative_to(_PERSONAS).as_posix() for path in _PERSONAS.rglob("*.md")
    )
    expected_persona_files = sorted(
        f"{persona.value}/{name}" for persona in Persona for name in ("role.md", "prompt.md")
    )

    assert (unloaded_tasks, persona_files, {"role.md", "prompt.md"} <= loaded) == (
        [],
        expected_persona_files,
        True,
    )


def test_no_generator_prompt_asks_for_a_non_defect() -> None:
    """Each non-defect is stated by its own prompt and named by no other generator prompt."""
    texts = {name: _read(name) for name in (*_GENERATOR_PROMPTS, _VERIFIER)}
    unstated = [subject for subject, home in _NON_DEFECTS if subject not in texts[home]]
    askers = sorted(
        (subject, name)
        for subject, home in _NON_DEFECTS
        for name in _GENERATOR_PROMPTS
        if name != home and subject in texts[name]
    )

    assert (unstated, askers) == ([], [])


def test_no_prompt_asks_for_an_advisory_id_or_takes_one_as_evidence() -> None:
    """All nine CVEs the session's findings cited were wrong, and six of them were VERIFIED.

    Advisories come from the scanners, which look them up; no prompt asks a model for one or
    lets a finding stand on one.
    """
    assert (
        sorted(
            (name, match.group(0))
            for name in _prompt_names()
            for match in _ADVISORY_ID_AS_EVIDENCE.finditer(_read(name))
        )
        == []
    )


def test_the_placeholder_advisory_verdict_states_the_prompts_policy() -> None:
    """The deterministic verdict said a dependency claim must cite a real advisory; it need not."""
    finding = Finding(
        severity="HIGH",
        location="pyproject.toml:1",
        title="Outdated FastAPI",
        description="Older releases carry unpatched CVEs (e.g., CVE-2023-xxxx).",
    )
    result = _check_placeholder_advisory_hallucination(finding)
    assert result is not None
    reason = result.invalidation_reason or ""

    assert (result.status, "must cite a real" in reason, "come from the scanners" in reason) == (
        "INVALIDATED",
        False,
        True,
    )


def test_the_prompts_carry_the_threat_model_and_the_evidence_bar() -> None:
    """Dropping one of these lets the class of false finding it stopped come back."""
    assert [(name, marker) for name, marker in _DECISIONS if marker not in _read(name)] == []


def test_the_masking_marker_rule_is_stated_once_by_the_reviewer_and_the_verifier() -> None:
    """The verifier said both that a marker claim is false and that it stands."""
    counts = {
        name: sum("<masked" in line for line in _read(name).splitlines())
        for name in (*_GENERATOR_PROMPTS, _VERIFIER)
    }

    assert {name: n for name, n in counts.items() if n} == {"tasks/review.md": 1, _VERIFIER: 1}


def test_the_marker_rules_name_only_the_markers_the_sanitizer_emits() -> None:
    """The verifier refuted claims about masks the review tool never writes.

    `mask_secrets` writes `<masked-kind>`. A bare `<masked>` is text a generator wrote, and
    `***REDACTED***` a literal in the code: the one true finding in the audit's sample, the
    `<masked>` default in `docs/commands/tls.md`, was refuted as a marker.
    """
    masked = mask_secrets(
        'token = "x9Kq2LmP7vR4"\npassword: "Zt8Yw3Qp1Lm"\nkey = "secret_4hT9wQ2zLp"'
    )
    marker = re.compile(r"<masked-[a-z-]+>")
    emitted = {"<masked-kind>", *marker.findall(masked)}
    rules = {name: _line_with(name, "<masked") for name in ("tasks/review.md", _VERIFIER)}
    unknown = {name: sorted(set(marker.findall(line)) - emitted) for name, line in rules.items()}
    other_masks = {
        name: [s for s in re.split(r"(?<=\.) ", line) if "<masked>" in s or "REDACTED" in s]
        for name, line in rules.items()
    }
    verifier = _read(_VERIFIER)

    assert (
        unknown,
        {
            name: [s for s in found if "the file's own text" not in s]
            for name, found in other_masks.items()
        },
        {name: bool(found) for name, found in other_masks.items()},
        (sorted(emitted), "<masked>" in masked),
        "Prompt Sanitizer Markers" in verifier,
        "`masked`" in verifier,
    ) == (
        {"tasks/review.md": [], _VERIFIER: []},
        {"tasks/review.md": [], _VERIFIER: []},
        {"tasks/review.md": True, _VERIFIER: True},
        (["<masked-kind>", "<masked-password>", "<masked-secret>", "<masked-token>"], False),
        False,
        False,
    )


def test_every_test_rule_keeps_a_real_credential_or_vulnerability_reportable() -> None:
    """The rules for tests disagreed with the verifier's section 7.

    The verifier said a test is a defect only when it cannot fail, and section 7 that a test can
    hold a genuine vulnerability; the reviewer called every literal in a test "not a secret".
    """
    texts = {name: _read(name) for name in (*_GENERATOR_PROMPTS, _VERIFIER)}
    with_rule = sorted(name for name, text in texts.items() if _TEST_RULE in text)

    assert (
        with_rule,
        [name for name in with_rule if _TEST_FILE_EXCEPTION not in texts[name].lower()],
        "A test, a doc or a config file can hold one" in texts[_VERIFIER],
    ) == (["tasks/code_review_prompt.md", _VERIFIER], [], True)


def test_security_rules_that_require_a_guard_name_an_untrusted_source() -> None:
    """A guard on trusted input is refuted, or LOW where the conventions require it."""
    assert [
        (name, label)
        for name, label in _SOURCE_BOUND_RULES
        if "untrusted" not in _line_with(name, label)
    ] == []


def test_the_served_code_review_prompt_asks_for_the_reviewer_reply() -> None:
    """MCP serves `code_review_prompt.md` alone, without `review.md` or the reply schema."""
    served = code_review_prompt(persona="devsecops", target="src/app")
    output = next((line for line in served.splitlines() if "JSON object" in line), "")
    named = set(re.findall(r"`(\w+)`", output))

    assert (
        "JSON object" in output,
        sorted(named - {"findings", "summary"} - _REVIEWER_FINDING_FIELDS),
        {"findings", "summary", "severity", "location", "title", "description", "fix"} <= named,
    ) == (True, [], True)


def test_no_review_page_names_part_of_the_reply_schema() -> None:
    """A review page is answered in the reply schema the persona system prompt carries.

    The MCP prompt's output line, written into `code_review_prompt.md`, reached every code page
    and named five of the schema's ten finding fields, without the criteria or the observed and
    expected values `review.md` requires.
    """
    pages = {
        kind.value: build_context_review_prompt(kind, "app/pages.py", 1, 1, "1\tx = 1\n")
        for kind in FileContextType
    }
    partial = sorted(
        (kind, line)
        for kind, page in pages.items()
        for line in page.splitlines()
        if len(named := set(re.findall(r"`(\w+)`", line)) & _REVIEWER_FINDING_FIELDS) > 2
        and named != _REVIEWER_FINDING_FIELDS
    )

    assert (partial, all("Return one JSON object" not in page for page in pages.values())) == (
        [],
        True,
    )


def test_the_measurement_runs_the_persona_the_baseline_ran() -> None:
    """The baseline session ran only DevSecOps; `--all` adds four whose own prompts are unchanged."""
    section = _measurement_section()

    assert (
        "devops review path <corpus>/files`" in section,
        "files --all" in section,
        "all from the DevSecOps persona" in section,
    ) == (True, False, True)


def test_the_masked_signature_counts_only_the_review_tools_markers(tmp_path: Path) -> None:
    """A bare `<masked>` is the file's own text, so a finding about one can be true.

    The counter took every `<masked` for a failure, the 10 baseline findings about a bare
    `<masked>` (the `docs/commands/tls.md` default among them) with the 36 about a marker. The
    known-positive check the task expects B to pass would have scored as a failure.
    """
    section = _measurement_section()
    script = re.search(r"```python\n(.*?)```", section, re.DOTALL)
    assert script is not None
    finding = {
        "references": [],
        "fix": "`x`",
        "severity": "LOW",
        "status": "VERIFIED",
        "verification_criteria": [],
    }
    findings = [
        {**finding, "location": "app/x.py:1", "title": "Marker", "description": "<masked-token>"},
        {**finding, "location": "docs/tls.md:24", "title": "Default", "description": "<masked>"},
    ]
    (tmp_path / "candidates.json").write_text(json.dumps({"findings": findings}))
    out = io.StringIO()
    with patch.object(sys, "argv", ["count", str(tmp_path)]), contextlib.redirect_stdout(out):
        code = compile(textwrap.dedent(script.group(1)), "SELF_IMPROVEMENT.md", "exec")
        exec(code, {"__name__": "count"})
    lines = out.getvalue().splitlines()
    counts = ast.literal_eval(lines[0][lines[0].index("{") :])

    assert (
        counts["masked"],
        [line for line in lines[1:] if "docs/tls.md:24" in line] != [],
        "`masked` 36" in section,
        "`masked` 46" in section,
    ) == (1, True, True, False)


def test_the_verifier_rates_severity_on_the_reviewers_bands() -> None:
    """The verifier's severity replaces the reviewer's, and it had no bands of its own.

    Its one verified security example, an untrusted request-body path traversal with every step
    quoted, said `MEDIUM`, where `review.md`'s bands say `HIGH` or `CRITICAL`. A list of every
    severity names the choices and anchors none.
    """
    band = re.compile(r"^\s*- \*\*(?:CRITICAL|HIGH|MEDIUM|LOW)\*\* — .+$", re.MULTILINE)
    verifier = _read(_VERIFIER)
    reviewer_bands = [line.strip() for line in band.findall(_read("tasks/review.md"))]
    example = re.search(r"```json\n(.*?)```", verifier, re.DOTALL)
    assert example is not None
    verified = re.findall(
        r'"status": "VERIFIED",.*?"severity": ([^\n]+),\n', example.group(1), re.DOTALL
    )

    assert (
        len(reviewer_bands),
        [line.strip() for line in band.findall(verifier)] == reviewer_bands,
        [sorted(re.findall(r'"(\w+)"', severity)) for severity in verified],
    ) == (4, True, [["CRITICAL", "HIGH", "LOW", "MEDIUM"]])


def test_no_example_reply_anchors_high_severity_or_confidence() -> None:
    """The reviewer's and the verifier's examples said `"severity": "HIGH"`, the verifier's `0.95`.

    534 of the session's 903 candidates were CRITICAL or HIGH. A list of every severity
    (`"CRITICAL" | "HIGH" | ...`) names the choices and anchors none.
    """
    fenced = re.compile(r"```json\n(.*?)```", re.DOTALL)
    anchor = re.compile(
        r'"severity":\s*"(?:CRITICAL|HIGH)"(?!\s*\|)|"confidence_score":\s*(?:0\.9\d*|1(?:\.0*)?)\b'
    )
    anchors = sorted(
        (name, match.group(0))
        for name in (*_GENERATOR_PROMPTS, _VERIFIER)
        for block in fenced.findall(_read(name))
        for match in anchor.finditer(block)
    )

    assert anchors == []


def test_the_persona_reply_schema_holds_only_what_a_reviewer_writes() -> None:
    """The persona system prompt carried all of `ReviewResult`'s schema, 8,220 characters.

    More than 30 of its fields belong to the pipeline (`status`, `verified`,
    `criteria_execution_results`), and asking for them invites a reviewer to fill them in.
    """
    schema = ReviewResult.model_json_schema()
    agent = PydanticAgent[ReviewResult](
        client=MagicMock(),
        name="DevSecOps",
        system_prompt=PERSONAS[Persona.DEVSECOPS].system_prompt,
        output_type=ReviewResult,
    )
    prompt = agent._build_system_prompt_with_tools()
    schema_text = json.dumps(schema, separators=(",", ":"))

    assert (
        set(schema["properties"]),
        set(schema["$defs"]["Finding"]["properties"]),
        sorted(schema["$defs"]),
        schema_text in prompt,
        "criteria_execution_results" in prompt,
        len(schema_text) < 2500,
    ) == (
        {"findings", "summary"},
        set(_REVIEWER_FINDING_FIELDS),
        ["Finding", "VerificationCriterion"],
        True,
        False,
        True,
    )


def test_a_reply_parses_as_before_whatever_fields_it_carries() -> None:
    """Fields left out of the schema are still parsed, so saved findings reload unchanged."""
    finding = {
        "severity": "MEDIUM",
        "location": "app/pages.py:12",
        "title": "Page drops its last item",
        "description": "The slice stops one short of the page end.",
        "fix": "return items[start:end]",
        "observed_value": "return items[start:end - 1]",
        "expected_value": "return items[start:end]",
    }
    pipeline_owned = {
        "status": "VERIFIED",
        "verified": True,
        "citation_line": 12,
        "confidence_score": 0.4,
        "criteria_execution_results": [{"command": "pytest", "passed": True}],
    }
    parsed = parse_review_response(json.dumps({"findings": [finding], "summary": "One defect."}))
    from_dict = _review_result_from_dict({"findings": [{**finding, **pipeline_owned}]})
    saved = SavedFinding.model_validate({**finding, **pipeline_owned, "persona": "devsecops"})
    assert parsed is not None and from_dict is not None

    assert (
        [(f.severity, f.location, f.observed_value, f.fix) for f in parsed.findings],
        parsed.summary,
        [(f.status, f.verified, f.citation_line, f.confidence_score) for f in from_dict.findings],
        len(from_dict.findings[0].criteria_execution_results),
        SavedFinding.model_validate(saved.model_dump()) == saved,
    ) == (
        [("MEDIUM", "app/pages.py:12", "return items[start:end - 1]", "return items[start:end]")],
        "One defect.",
        [("VERIFIED", True, 12, 0.4)],
        1,
        True,
    )


def test_this_repositorys_review_conventions_state_its_threat_model_within_the_cap() -> None:
    """The file is cut at the cap when it is read, so a rule past it never reaches a model.

    devops-cli reviews the user's own repositories, itself included. Listing those as trusted
    beside "repositories under review" as untrusted left the verifier to refute, as trusted
    input, a defect where a review runs or reads the tree under review (#946).
    """
    own = (_ROOT / ".devops" / "review.md").read_text(encoding="utf-8")

    assert (
        "## Threat model" in own,
        "**Trusted here**" in own,
        "**Untrusted here**" in own,
        "even when it is the user's own" in " ".join(own.split()),
        len(own) <= DEFAULT_REVIEW_CONVENTIONS_MAX_CHARS,
    ) == (True, True, True, True, True)
