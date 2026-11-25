## Problem

The test job of main fails since 9dfe03e3e (#6794, #6736). Two tests of `tests/roadmap/refine/test_roadmap_refine_block_markers.py` fail in shard 5 of "Tests & Coverage" (run 45069872720):

```text
FAILED ...::test_a_block_that_a_person_opens_above_the_section_leaves_one_section_over_three_rounds[fence]
FAILED ...::test_a_block_that_a_person_opens_above_the_section_leaves_one_section_over_three_rounds[pre]
2 failed, 5566 passed, 5 skipped
```

#6792 (#6729) makes `closed_body` in `src/devops_cli/roadmap/stores/store.py` close a block that the body leaves open at its end, before the record. #6794 (#6736) makes the readers end such an open block at the job blocks at its end. Each PR passed alone. Together, a record write closes the open block of a person after the job block. The job block is then a quote in a closed block, and the next refine round adds a second section. The review of #6794 found this conflict before the merge (https://github.com/dan-petty/devops-cli/pull/6794#issuecomment-7082969636). The two PRs merged in an order that did not rebase #6794 onto #6792.

## Expected

A record write keeps each job block readable: `closed_body` closes each block open before a job block marker (`close_blocks_before_markers`, #6736), then the block open at the end. The test job of main passes.

## Acceptance criteria

- The two failing tests pass.
- Test first: `with_record` on a body with a job block inside an open fence or `<pre>` of a person gives a body where `job_block_bounds` finds the job block. The test fails on the base.

## Dependencies

None. Related: #6729, #6736.


<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P1-High", "Status": "In Review", "Value": "High", "claim.replaced_status": "New"} -->
