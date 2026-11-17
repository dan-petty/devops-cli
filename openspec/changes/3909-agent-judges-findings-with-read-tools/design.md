# Design

## Decisions

- **The judge runs on pydantic-ai through the project's `build_agent` factory and the toolset helper `create_function_toolset` of `src/devops_cli/ai/toolsets/__init__.py`.**: The pins give the typed output, the tool schema and the test models, and the project already builds every other agent through that one factory.
- **The agent registers exactly four read-only tools: a store lookup, a repository search, the component list and an exact or regular-expression match over stored text.**: Each answer names a record id or a path, so the citation check can verify what the model read, and a test counts the four and refuses a fifth.
- **The citation check is a plain function after the agent returns, and the agent holds no field and no tool that files a candidate.**: ADR 0005 gives model output no field that changes state, and a test checks the drop and the count in code.
- **The judge reads through the narrow `ReadOnlyCorpus` protocol that the judge module defines, and not through the Qdrant client.**: A test doubles the corpus and reaches no network, and the store that #3906 delivers satisfies the protocol at the call site.
- **The judge lives in `src/devops_cli/research/judge.py`, beside the sweep and its models.**: It judges the records of the research sweep and reads the component list of `src/devops_cli/research/models.py`; `src/devops_cli/ai/research/` holds the epistemic research commands, which judge nothing.
- **A narrow instruction-override detector joins `scan_injection_line`, and it matches an override addressed to the reader such as "ignore your rules".**: The issue's test phrase is plain English that the four existing detectors pass, and the second-person form keeps the existing INJ002 case at one finding.
- **A record that the scanner flags is withheld from the model and named in the report.**: A warning inside the prompt does not stop the instruction, and a person can tell a flagged advisory from a missing one only when the report names it.
- **affects_us holds yes, no or unknown, and a record with thin evidence gets unknown.**: The evaluation gate fails on a false no, so the judge needs a way to say that it cannot tell.
- **The per-sweep record limit and the daily token limit are settings of the research job, counted by the judge.**: A test sets a low limit and checks the stop with no outside service, and each stop names its setting and value.
- **The two new variables join `_VARIABLES_OF_LATER_SETTINGS` in `tests/security/test_config_declarations.py`, and the settings documents are regenerated rather than edited.**: That file holds the census of declared variables, and `docs/ENV_VARS.md` and `docs/CONFIGURATION.md` are output of `uv run devops docs generate`, which `uv run devops ci docs` checks.
- **The rate function is named `judge_agreement_rate`, and `src/devops_cli/ai/run_store.py` stays unchanged.**: That module already holds `agreement_rate` at line 620, and the research judge needs its own rate over labeled findings.
- **The 20 labeled findings are a checked-in constant, and the live run is a marked test module.**: The labels stay stable and a review reads them, the offline tests spend no model tokens, and the live run needs the gateway.

## Rejected alternatives

- **Match the bare phrase "ignore previous instructions" in the new detector.**: `tests/security/test_prompt_injection.py:49:assert len(findings) == 1` counts the findings of that exact phrase, so a second match would break the existing INJ002 case.
- **Hand-edit `docs/ENV_VARS.md` with the two new settings.**: `CONTRIBUTING.md:204:| Environment variable |` says the command output and `docs/ENV_VARS.md` are generated from the declarations, and the docs row of the gate refuses a generated document that is not the generator's output.
- **Declare the two settings with no environment-variable marker on the field, so the variable census stays as it is.**: The declaration test compares the variables of the settings at `tests/security/test_config_declarations.py:136:_VARIABLES_OF_LATER_SETTINGS = frozenset(`, so a setting that code reads without its variable would fail it.
- **One generic search tool for the agent.**: It cannot name the record that it read, so the citation check cannot verify the answer against the store.
- **A tool of the agent that files the intake candidate.**: `docs/adr/0005-review-findings-come-from-tools-not-models.md` says that model output has no field that can create, move, re-rate or change the state of a finding, and the agent can skip a tool call.
- **A pydantic validator on the output model that checks the citations.**: It needs the store inside the model process, and the model then sees the check and can retry around it.
- **Warn the model about the instruction in the prompt instead of withholding the record.**: The issue's test requires no tool call and no output field for that record, and a warning in the prompt does not stop the instruction.
- **A boolean affects_us field.**: The evaluation gate fails on a false no, and thin evidence needs a way to say that the judge cannot tell.
- **A confidence score instead of the three-valued field.**: The gate counts labels and not scores, and a score adds a threshold to tune.
- **Use the budget store of #3066 for the two limits.**: #3066 is open and bounds the model use of a repository and of a day for the Service; this change needs one record count and one token count for its own run.
- **Run the labeled evaluation in every CI job.**: It spends model tokens on each push, and `docs/adr/0004-ci-is-the-authoritative-gate.md` keeps the model token costs bounded, so the live run is a manual process.
