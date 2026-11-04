# Design

## Decisions

- **Record the matching paths of each negative-search literal in a CaseFacts mapping that check_proposal takes as a keyword with a default of no record.**: It follows the probes input: the job records it once, the replay reads it from its case, and a caller with no checkout still gets the created-module check.
- **Carry the mapping in CaseFacts with an empty default.**: The 37 recorded cases keep their shape, and only the new case names evidence.
- **Read the literal and the relative paths with one parser in the form gate, which reuses the option list of the shell policy.**: A second git grep parser would drift from the form check that already refuses pipes, redirects and unsupported options.
- **Compare the literal with the import path of each created source path under src/devops_cli/.**: It catches a move of the stage modules, such as the one in the #3378 scenarios, without reading the content of a file that the plan creates.
- **Ask the planner to call search_code with the literal and to quote the hit count in feasibility.**: The planner can correct the plan before the gate refuses it, and the quote ties the plan to the staged commit.
- **Hold the case of the move of the stage modules in tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/ and assert it in tests/roadmap/test_roadmap_stage_negative_search.py.**: The replay then runs the recorded plan and its recorded evidence offline, with no git call and no network.

## Rejected alternatives

- **Run git grep inside check_proposal.**: The replay calls no git, and plan_check judges a change folder with no checkout of the staged commit.
- **Record only the total hit count of a literal.**: A total cannot show whether a hit sits on a path that the plan creates, which is the fault of the bare prefix.
- **Accept every literal that has a staged hit.**: The literal devops_cli.roadmap.stage of the move has a staged hit on the old import lines and still fails after the move.
- **Add a new scanner beside git grep.**: The issue records git grep and the existing search_code and references tools as the covering tool, at about 10k tokens and 1 hour to build.
