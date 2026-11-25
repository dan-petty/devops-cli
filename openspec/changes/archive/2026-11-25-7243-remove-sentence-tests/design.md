# Design

## Decisions

1. **A fixed sentence goes.** A test goes when it holds a sentence, a phrase, a heading, a word list or a count of a real document, prompt, template or skill, or when it compares the text of two such files.
2. **A contract between code and prompt stays.** A test stays when its expected values come from the source code and the prompt or document must name each of them: the fields of a reply model, the values of an enum, a limit, the names of the tools. It fails when code and prompt disagree, which is a defect of the product. 21 such tests stay, for example `test_each_list_of_keys_of_the_reply_is_the_fields_of_a_model` in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` and `test_the_tools_prompt_names_exactly_the_tools_of_the_toolbox`.
3. **A generic rule stays.** Link checks, path and command checks, the size cap of `AGENTS.md`, the equality of a pointer stub and the generator output, and the equality of a skill in each root stay.
4. **A test of generator logic stays.** `tests/commands/test_instruction_generator.py` keeps the tests that give a sample project and check the detected toolchain or the detected checks in the output. It loses the tests that only find a fixed sentence of the template.
5. **A test of code that takes a real file as input stays.** Examples: the reader tests of `tests/roadmap/test_roadmap_plan_read.py`, which read archived change folders, and `test_each_route_names_a_document_and_sections_that_exist`, because the step reads these sections by their titles at run time.
6. **One line stays in 12 tests of code.** Each of these tests checks code and also finds one sentence of a prompt or a document. Most of the lines are safety sentences, for example "never an instruction" in `tests/roadmap/intake/test_roadmap_intake_untrusted_text.py`, where the test is the proof that untrusted text reaches the model as data. The owner can remove these lines also.
7. **A removed proof of a scenario becomes a command.** Five requirements named a removed test as the proof. Each scenario now runs `git grep` on the document.

## Rejected alternatives

- **Remove each of the 197 census rows**: rejected, because 21 of them compare a prompt with a value of the source code, such as `StageProposal` fields in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. A reply that the prompt describes and the schema refuses is a defect that these tests find.
- **Remove the rule of the stage check that asks for a prompt sentence test in this change**: rejected, because it changes source code and two prompts (`PROMPT_RULE_TEST` in `src/devops_cli/roadmap/stage/stage_change.py`), and this change removes tests only (#7246).
- **Correct each living spec that describes a sentence check**: rejected for this change, because only five requirements name a removed test as a command or by its name. The other scenarios are part of #7246.
