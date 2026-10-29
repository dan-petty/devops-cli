# Tasks

## 1. The benchmarks name each server by host and port

- [ ] 1.1 Write the failing tests for a dry run, a CLI run through a stubbed Ollama, a failed embedding run, a `model@endpoint` embedding run and a server with no origin
  - Verification: `uv run devops ci test tests/test_ai_benchmark.py tests/test_embedding_benchmark.py`
- [ ] 1.2 Add `server_label` in `src/devops_cli/ai/benchmark/server_label.py`, and use it in both runners and in the setup of the kept run
  - Verification: `uv run devops ci test tests/test_ai_benchmark.py tests/test_embedding_benchmark.py tests/test_embedding_benchmark_failure.py`
- [ ] 1.3 Say in the help of `--servers` that a report names a server by `host[:port]`, and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] 2.1 Archive the change
  - Verification: `uv run devops openspec archive 2481-benchmark-server-labels`

## Workflow follow-up

- The chat benchmark names a model by its `model@endpoint` entry, which can hold a password: #2643.
- Pending a person: if a server URL held `user:password` in `ai.ollama_urls`, `--servers` or a `model@endpoint` entry, change that password. Then delete the old files in `<data>/benchmarks` and the kept `ai-benchmark` runs. They hold the URL as it was configured.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
