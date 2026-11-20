# Proposal: #6422

## Why
`tests/k8s/test_lease.py::test_a_pod_that_waits_takes_the_lease_only_after_the_holder_gives_it_back` fails at random (#6422). In shard 3 of Tests & Coverage on PR #6403 (job 135563733782), `release()` of the old pod returned `False`, and the new pod held the Lease. The test called `lease_clock.leave()` before `await old.release()`. After `leave()`, the fake clock has one party, so each sleep of the waiting pod moves the clock at once. While the read of `release()` waits for its thread, the waiting pod can sleep past the 15 s duration of the Lease and take it. `release()` then reads another holder and returns `False`. The result depends on the scheduler of the host.

Closes #6422.

## What Changes
- The handover test calls `lease_clock.leave()` after `await old.release()` returns. During the release, the clock keeps two parties and does not move, so the waiting pod takes the Lease only after the old pod gives it back.
- The docstring of `_LeaseClock.leave()` states that the test calls it only after the last API call of the holder that stops.
- The change alters no behavior that a consumer sees. It changes one test file, so it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. `LeaseHolder` in `src/devops_cli/k8s/lease.py` does not change.

## Impact
- The handover test gives the same result on each run, so it does not fail a pull request that does not change the Lease code.
- No command, setting, manifest or product code changes. The change fits one pull request.

## Feasibility
- The log of job 135563733782 shows `At index 1 diff: False != True` at `tests/k8s/test_lease.py:111`: `given_back` was `False`.
- A probe outside the repository made the read of `release()` wait 50 ms in its thread. With `leave()` before `release()`, `release()` returned `False` in 20 of 20 runs. With `leave()` after `release()`, it returned `True` in 20 of 20 runs.
- On a host with 16 CPUs and no other load, the old order passed 500 of 500 runs in one process, and 2,000 of 2,000 runs in 4 xdist workers. With 8 pytest processes on 4 CPUs and coverage, as on a loaded runner, the old order failed in 4 of 200 runs of a shell loop, and in 18 and 11 of 2,000 runs in 8 xdist workers. Each failure showed `At index 1 diff: False != True`.
- The runs of the new order are in the comment of the pull request.

## Existing Tool Considered
pytest and the `_LeaseClock` of the test cover the need. The change adds no dependency and builds no tool. Cost: about 120k tokens and 1.5 hours, most of it for the reproduction.
