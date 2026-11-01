# Tasks

## 1. Add EmbeddingsError guard for empty Ollama URL list

Reads: none. Changes: `src/devops_cli/ai/rag/embeddings.py`, `tests/ai/rag/test_embeddings.py`.

- [ ] 1.1 Write a test that constructs EmbeddingsEngine with ai.provider set to ollama and ai.ollama_urls set to an empty list. Call embed_texts with one text. Assert that EmbeddingsError is raised and its message contains the embedding_no_provider text. Assert that ZeroDivisionError is not raised, and verify that `uv run devops ci test tests/ai/rag/test_embeddings.py` fails on the base
- [ ] 1.2 In _embed_ollama, after urls = self._get_ollama_urls(), add a guard: if urls is empty, raise EmbeddingsError with ERRORS.rag.embedding_no_provider formatted with self.model and self.ai_config.provider, and details with model and provider. This guard sits before any batch computation, and verify that `uv run devops ci test tests/ai/rag/test_embeddings.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Replace intake handoff with gh issue create

Reads: none. Changes: `.github/workflows/defect-pr-hardening-audit.yml`, `tests/workflows/test_defect_pr_hardening_audit.py`.

- [ ] 2.1 Write a test that reads the workflow YAML file. Parse the handoff step. Assert that the step's run block contains gh issue create. Assert that the step's run block does not contain devops roadmap intake, and verify that `uv run devops ci test tests/workflows/test_defect_pr_hardening_audit.py` fails on the base
- [ ] 2.2 In the handoff step of .github/workflows/defect-pr-hardening-audit.yml, replace the uv run devops roadmap intake command with gh issue create. Pass the title, the body file, and a label for priority. Keep the existing INTAKE_BODY heredoc and the sed substitution. Remove the uv run prefix since gh is a runner binary, and verify that `uv run devops ci test tests/workflows/test_defect_pr_hardening_audit.py` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
