# Design

## Decisions

- **Create stand-in files on PATH in the fixture, the same mechanism scanner_fake uses internally, rather than using scanner_fake directly.**: The test uses tool_executor_fake (a plain ToolExecutorFake) in most cases and needs only the PATH stand-ins so that shutil.which finds the tool. scanner_fake carries recorded answers that this test does not need. The design of #1982 confirms this: a test that needs a scanner missing gives it a PATH without the program.
- **Keep the fixture autouse and scoped to this test file.**: The fixture is local to tests/test_scanner_tool_executor.py and is not shared. Making it autouse keeps every test in the file covered without changing each test's signature.

## Rejected alternatives

- **Use scanner_fake directly in the test file.**: The test uses tool_executor_fake (a plain ToolExecutorFake) in most cases. scanner_fake is a ToolExecutorFake that carries recorded answers for Semgrep, Gitleaks, Bandit and osv-scanner. The test needs only the PATH stand-ins, not the recorded answers. Using scanner_fake would change the executor the test scripts and break the test's assertions on tool_executor_fake.requests.
- **Keep the shutil.which patch and add a noqa or exception to the convention.**: docs/TESTING.md states: A test doubles only edges. Everything inside the process runs for real. Patching a stdlib or SDK object itself, such as subprocess.run or time.sleep, is a fallback for stdlib edges only. The stand-in-on-PATH mechanism is the established pattern since #1982 and requires no exception.
