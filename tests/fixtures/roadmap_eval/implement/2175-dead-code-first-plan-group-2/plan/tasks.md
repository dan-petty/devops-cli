# Tasks

## 1. Delete thinking_detected from streaming.py

Reads: none. Changes: `src/devops_cli/ai/client/streaming.py`.

- [ ] 1.1 Write a test that asserts StreamingTokenProcessor has no thinking_detected attribute. The test fails before the deletion and passes after, and verify that `! git grep -n -w thinking_detected src/ tests/ docs/` fails on the base
- [ ] 1.2 Delete the thinking_detected property from StreamingTokenProcessor. Remove any import or constant that only this property uses. Remove any test that only calls thinking_detected, and verify that `! git grep -n -w thinking_detected src/ tests/ docs/` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. Delete _get_ollama_semaphore from unified.py

Reads: none. Changes: `src/devops_cli/ai/client/unified.py`.

- [ ] 2.1 Write a test that asserts LLMClient has no _get_ollama_semaphore attribute. The test fails before the deletion and passes after, and verify that `! git grep -n -w _get_ollama_semaphore src/ tests/ docs/` fails on the base
- [ ] 2.2 Delete the _get_ollama_semaphore classmethod from LLMClient. Remove any import or constant that only this method uses. Remove any test that only calls _get_ollama_semaphore, and verify that `! git grep -n -w _get_ollama_semaphore src/ tests/ docs/` passes
- [ ] 2.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. Delete unique_thinking from thinking_stream.py

Reads: none. Changes: `src/devops_cli/ai/thinking_stream.py`.

- [ ] 3.1 Write a test that asserts ThinkingStreamProcessor has no unique_thinking attribute. The test fails before the deletion and passes after, and verify that `! git grep -n -w unique_thinking src/ tests/ docs/` fails on the base
- [ ] 3.2 Delete the unique_thinking property from ThinkingStreamProcessor. Remove any import or constant that only this property uses. Remove any test that only calls unique_thinking, and verify that `! git grep -n -w unique_thinking src/ tests/ docs/` passes
- [ ] 3.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 4. Delete _validation_error_key from settings.py

Reads: none. Changes: `src/devops_cli/config/settings.py`.

- [ ] 4.1 Write a test that asserts the settings module has no _validation_error_key name. The test fails before the deletion and passes after, and verify that `! git grep -n -w _validation_error_key src/ tests/ docs/` fails on the base
- [ ] 4.2 Delete the _validation_error_key function from settings.py. Remove any import or constant that only this function uses. Remove any test that only calls _validation_error_key, and verify that `! git grep -n -w _validation_error_key src/ tests/ docs/` passes
- [ ] 4.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 5. Delete grid_width from schema.py and run CI

Reads: none. Changes: `src/devops_cli/grafana/schema.py`.

- [ ] 5.1 Write a test that asserts Dashboard has no grid_width attribute. The test fails before the deletion and passes after, and verify that `uv run devops ci` fails on the base
- [ ] 5.2 Delete the grid_width property from Dashboard. Remove any import or constant that only this property uses. Remove any test that only calls grid_width, and verify that `uv run devops ci` passes
- [ ] 5.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
