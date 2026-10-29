# Proposal

## Why

Issue #2481: the AI benchmarks name each server by the text of its configured URL, and that text keeps the userinfo.

- A URL in `ai.ollama_urls` or in `--servers` can hold userinfo. This is valid configuration. httpx2 sends the userinfo as Basic authentication to an Ollama behind an authenticating proxy.
- `BenchmarkRunner` writes the raw URL in the `Workers:` line and in the `backend=` text of a dry run. It also writes it as the `server` of each task response, peer grade and server summary.
- `_save_report` writes `report.model_dump_json()` to `<data>/benchmarks/<session>-benchmark.json`. The command also keeps the report as a run, and the setup of that run lists `--servers` as typed.
- `EmbeddingBenchmarkRunner` writes the raw URL after `on` in its progress lines and in its log line. It also writes it as the `server` of each result, in the saved report.

#1110 names the server of an AI reply by the httpx2 origin of the URL that the client called. The benchmark runners were not sites of #1110.

## What Changes

- One helper, `server_label(url)` in `ai/benchmark/server_label.py`, gives the text `host[:port]` of a server URL. It calls `get_url_origin` and `origin_label` of #1110. A URL with no origin gives `unknown`.
- `BenchmarkRunner` keeps the configured URLs in `self.servers` for the requests. It writes the label in the `Workers:` line, in the dry-run `backend=` text, in each `server` field and in the server summaries.
- `EmbeddingBenchmarkRunner` writes the label in its progress lines, in its log line and in the `server` of each result. This holds for a configured server and for the endpoint of a `model@endpoint` entry.
- The setup of a kept run lists the labels of `--servers`.
- The help of `--servers` says that a report names a server by `host[:port]`. `devops docs generate --sync-readme` writes the same text in the documents.
- This change alters output and report fields that a consumer reads, so it has the spec delta `ai-reply-server`.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-reply-server`: a benchmark names each server by the `host[:port]` of its URL, never by the URL.

## Impact

- `src/devops_cli/ai/benchmark/server_label.py` (new), `runner.py` and `embedding_runner.py`.
- `src/devops_cli/commands/benchmark.py` and `src/devops_cli/lang/en/help.py`.
- `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `docs/commands/ai.md`.
- `tests/test_ai_benchmark.py` and `tests/test_embedding_benchmark.py`.
- `openspec/specs/ai-reply-server/spec.md`.

## Feasibility

- The leak is real on `origin/main` at `aba6069f`. An offline dry run, `BenchmarkRunner(models=["m"], tasks=[BENCHMARK_TASKS[0]], is_dry_run=True, servers=["http://bench-user:FAKE-2481-value@example.com:11434"]).execute()`, printed the whole URL in the `Workers:` line and in the `backend=` text. The `server` of each response, peer grade and server summary was the whole URL, and `report.model_dump_json()` held `FAKE-2481-value`.
- The new failing tests show the same leak for the embedding benchmark. They show it in the progress line, the log line, the `server` of each result and the saved report. A CLI run through a stubbed Ollama showed it for the saved report and for the setup of the kept run.
- The stub received `Authorization: Basic` with the user and the password on each request to the server. Thus the requests need the full URL, and only the names need the label.
- `get_url_origin("http://bench-user:FAKE-2481-value@example.com:11434")` gives `Origin(scheme='http', host='example.com', port=11434)`, and `origin_label` of it gives `example.com:11434`. `get_url_origin("not-a-url")` gives `None`. httpx2 2.13.1 is the pin in `pyproject.toml`.
- The error of a refused `--servers` entry is already masked. For `ftp://bench-user:FAKE-2481-value@example.com:2121`, the message shows `ftp://<masked-user>:<masked-password>@example.com:2121`, so this change leaves it as it is.
- The error text of a failed embedding run is already masked. A probe of a failed run gave `http://<masked-user>:<masked-password>@example.com:11434/api/embed failed`, so no password is in `error`. The text of a failed chat call has no URL.
- The same defect exists for a `model@endpoint` entry in the chat benchmark, where the entry is the name of the model. It is a different change, because the entry is also the key of the model in the report. Issue #2643 asks for it.

## Existing Tool Considered

httpx2 reads the URL that the client sends, and its `Origin` has no userinfo. `get_url_origin` (#1112) and `origin_label` (#1110) are the readers that the AI client already uses for the same text. The change builds no parser. `server_label` is a call of these two with the text `unknown` for no origin. It deletes the raw URL text from every name that the two runners write.
