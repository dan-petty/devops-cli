"""The cap, the trailer and the mask of one planner run (#4006, ADR 0018)."""

from __future__ import annotations

import re

from devops_cli.roadmap.run_output import (
    MAX_RUN_OUTPUT_BYTES,
    MAX_RUN_OUTPUT_LINES,
    cap_run_output,
    quote_run,
)

_TRAILER = re.compile(r"^\[truncated: (\d+) bytes and (\d+) lines omitted\]$")


def test_a_long_output_is_cut_within_the_caps() -> None:
    text = "".join(f"line {number:04d}\n" for number in range(400))
    capped = cap_run_output(text)

    assert (
        len(capped.text.encode("utf-8")) <= MAX_RUN_OUTPUT_BYTES,
        len(capped.text.splitlines()) <= MAX_RUN_OUTPUT_LINES,
        capped.text.splitlines()[-1].startswith("[truncated: "),
    ) == (True, True, True)


def test_the_trailer_names_the_omitted_bytes_and_lines() -> None:
    text = "".join(f"line {number:04d}\n" for number in range(400))
    capped = cap_run_output(text)

    (trailer,) = (_TRAILER.match(capped.text.splitlines()[-1]) for _ in (0,))
    kept_bytes = len(capped.text[: capped.text.rindex("[truncated: ")].encode("utf-8"))
    kept_lines = len(capped.text.splitlines()) - 1

    assert trailer is not None
    assert (
        int(trailer.group(1)),
        int(trailer.group(2)),
        kept_bytes + int(trailer.group(1)),
        kept_lines + int(trailer.group(2)),
    ) == (
        len(text.encode("utf-8")) - kept_bytes,
        len(text.splitlines()) - kept_lines,
        len(text.encode("utf-8")),
        len(text.splitlines()),
    )


def test_a_short_output_keeps_every_line_and_no_trailer() -> None:
    text = "one\ntwo\nthree\n"

    assert cap_run_output(text).text == text


def test_a_token_on_stderr_is_masked_before_the_cut() -> None:
    token = "ghp_" + "a" * 36
    capped = cap_run_output(f"GITHUB_TOKEN={token}\n")

    assert "<masked-github-token>" in capped.text
    assert "a" * 36 not in capped.text


def test_a_private_key_whose_end_is_past_the_cap_is_masked_whole() -> None:
    body = "\n".join(f"keyline{number:04d} = {number}" for number in range(600))
    begin = "-----BEGIN " + "RSA PRIVATE KEY-----"
    end = "-----END " + "RSA PRIVATE KEY-----"
    text = f"{begin}\n{body}\n{end}\n"

    capped = cap_run_output(text)

    assert (
        "<masked-private-key>" in capped.text,
        begin in capped.text,
        "keyline0000" in capped.text,
    ) == (True, False, False)


def test_the_quote_block_opens_with_a_fence_longer_than_the_text() -> None:
    text = "a line\n```\nthe last line\n"
    block = quote_run(["devops", "k8s", "get", "pods"], 1, text, "")
    lines = block.splitlines()

    assert lines[0] == "````"
    assert lines[1] == "$ devops k8s get pods"
    assert lines[2] == "exit 1"
    assert lines[-1] == "````"
    assert "```" in lines


def test_a_line_over_the_cap_leaves_only_the_trailer() -> None:
    capped = cap_run_output("x" * 200, limit_bytes=100)

    assert capped.text == "[truncated: 200 bytes and 1 lines omitted]\n"


def test_a_trailer_that_pushes_the_text_over_the_cap_drops_kept_lines() -> None:
    text = "".join(f"line {number:04d}\n" for number in range(1000))

    capped = cap_run_output(text, limit_bytes=100)

    assert (
        len(capped.text.encode("utf-8")) <= 100,
        capped.omitted_lines > 0,
        capped.text.endswith("omitted]\n"),
    ) == (True, True, True)


def test_the_quote_block_joins_stdout_and_stderr_with_a_newline() -> None:
    block = quote_run(["cmd"], 0, "out", "err\n")

    assert "out\nerr\n" in block
