### Friction

`tests/test_scanner_tool_executor.py` has an autouse fixture of its own, `scanners_installed`, that patches `shutil.which` so that the review scanners look installed. docs/TESTING.md says that tests double only process edges, through the shared fakes. Since #1982, `scanner_fake` puts an executable stand-in for each recorded scanner first on PATH and patches no `shutil` or `subprocess` name.

### What should happen

`tests/test_scanner_tool_executor.py` makes the scanners findable with stand-ins on PATH, as `scanner_fake` does, or with `scanner_fake` itself, and patches no `shutil` name.

### Evidence

- Found during #1982 on 2026-10-24: the fixture `scanners_installed` in `tests/test_scanner_tool_executor.py` patches `shutil.which`.

### Order

After #1982.


Source: https://github.com/dan-petty/devops-cli/issues/1982

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The test file tests/test_scanner_tool_executor.py makes review scanners appear installed by patching shutil.which. Since #1982, the shared scanner_fake fixture makes scanners findable by putting executable stand-ins on PATH and patches no shutil or subprocess name. The test file violates the convention in docs/TESTING.md that a test doubles only process edges through shared fakes. The fixture must be replaced with stand-ins on PATH so that no shutil name is patched.

### Acceptance criteria
- Criterion 1: The autouse fixture scanners_installed no longer patches shutil.which.
  Verification: Run grep -n 'shutil.which' tests/test_scanner_tool_executor.py and confirm no match. Run uv run pytest tests/test_scanner_tool_executor.py -x and confirm all tests pass.
- Criterion 2: The scanners are made findable by placing executable stand-in files on PATH, as scanner_fake does.
  Verification: Run uv run pytest tests/test_scanner_tool_executor.py -x -v and confirm all tests pass. Inspect the fixture and confirm it creates files in a temp directory and prepends that directory to PATH, with no monkeypatch.setattr on shutil.
- Criterion 3: No test in the file patches a shutil or subprocess name.
  Verification: Run grep -n 'monkeypatch.setattr.*shutil\|monkeypatch.setattr.*subprocess' tests/test_scanner_tool_executor.py and confirm no match.

### Key questions
- **What does scanner_fake do to make scanners findable on PATH?**: It puts an executable stand-in for each recorded scanner first on PATH. It patches no shutil or subprocess name. [sources: docs/TESTING.md:179, openspec/changes/archive/2026-10-24-1982-scanner-fake-through-tool-executor/design.md]
- **Should the test use scanner_fake directly or create its own stand-ins on PATH?**: The test uses tool_executor_fake (a plain ToolExecutorFake) in most cases, not scanner_fake (which carries recorded answers). The test needs only the PATH stand-ins so that shutil.which finds the tool. It should create its own stand-ins on PATH, the same mechanism scanner_fake uses internally, without requiring the recorded answers of scanner_fake. (proposed) [sources: tests/test_scanner_tool_executor.py:55, docs/TESTING.md:179]
- **Is there a dependency on another issue?**: Yes. The issue states it must come after #1982, which rebuilt scanner_fake over ToolExecutorFake and established the stand-in-on-PATH pattern. [sources: openspec/changes/archive/2026-10-24-1982-scanner-fake-through-tool-executor/tasks.md:23]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": null, "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "implement.branch": "test/2116-the-scanner-executor-tests-find-the", "implement.job": "devops-cli-runner-20261101-041624-6a80", "implement.job_digest": "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e", "implement.job_state": "succeeded", "implement.pr": "2977", "implement.spend": "{\"requests\": 5, \"input_tokens\": 53203, \"output_tokens\": 16612}", "implement.stopped": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "9fbdc1f192fe1f508a93e6f581004bfc95eb185bfc88155af0f39596dbd2cb80", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "43542fe55cfee892b1df0ff5204c10d7e283db80dc992a50697bde434a81584a", "stage.branch": "test/2116-the-scanner-executor-tests-find-the", "stage.file_cap": null, "stage.groups": "[[\"Replace shutil.which patch with PATH stand-ins\", 2346]]", "stage.needs_split": null, "stage.pr": "2977", "stage.sha": "d3f7c2a11fd23902078e8eaba0db52d3a9b436e1"} -->
