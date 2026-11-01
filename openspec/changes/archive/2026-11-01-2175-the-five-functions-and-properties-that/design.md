# Design

## Decisions

- Delete `network.get_ollama_semaphore`, `network.ollama_semaphores` and `network.ollama_sem_lock` with `LLMClient._get_ollama_semaphore`. The method is the only caller of the function, and the function is the only user of the two module variables, apart from their reset in `reset_ollama_slots`. The issue asks for the deletion of "any import or constant that only they use". If the function stayed, the change would leave a new dead function behind.
- Verify the change with `git grep -n -w <name>` that prints nothing, with the existing tests of the touched modules, and with `uv run devops ci`. The change keeps behavior, so it adds no test. A test that names a deleted name would also make the `git grep` check of the issue fail.

## Rejected alternatives

- A test for each deleted name that asserts the attribute is gone (a tombstone test). Issue #1871 deleted twelve such tests, because they pin the names of deleted things for ever. Such a test also contains the name, so the `git grep` check of the issue could not pass.
- A dead-code tool as a gate. Issue #1910 rejects `vulture` as a gate: the trial needed 12 decorator patterns and 7 name patterns first.

The golden sets of `devops roadmap eval` (`tests/fixtures/roadmap_eval/`) keep the issue text, the plan and the diff of #2175 as records, so they name the five definitions. Every `git grep` of this change leaves that folder out with `:!tests/fixtures/roadmap_eval`. No code, test or document outside it names them.
