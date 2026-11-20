# Design

## Decisions

- `_LeaseClock.sleep` awaits `asyncio.sleep(0)` after its own future is done. A real `asyncio.sleep` with a delay always suspends the task, and the fake must do the same. A pod that sleeps alone wakes itself, so before this change its sleep did not suspend. When `asyncio.to_thread` also returned with no yield, the pod made a full try in one step of the loop.
- The yield comes after `_wake`, which sets each mark that the clock reaches. So the wakeup of a task that waits for a mark is in the ready queue before the sleeper resumes, and that task reads the state first. This order does not depend on the thread timing of the host.
- The new test `test_a_task_that_waits_for_a_mark_reads_before_the_sleeper_goes_on` uses a sleeper with no thread calls. Without the yield, the sleeper does all its sleeps in one step, so the test fails on each run, not at random.
- `LeaseHolder` in `src/devops_cli/k8s/lease.py` does not change. With the real `asyncio.sleep`, each try of a pod starts in a new step of the loop. A `to_thread` call that returns with no yield is correct behavior of asyncio.

## Rejected alternatives

- Set the marks in `_wake` before the sleepers wake, as the refined design of #6545 proposed: no task awaits the future of a sleeper that is alone, so the order in `_wake` changes nothing. The new test still failed with `[2.0, 4.0, 6.0]`.
- Set the future of each sleeper through `loop.call_soon`: it also makes the sleep suspend, but a sleeper that a test cancels before the callback runs needs a guard. `asyncio.sleep(0)` gives the same order with one line.
- Replace `_LeaseClock` with looptime: it adds a dependency and changes each Lease test for a fault of one line in the fake.
- A retry, a skip or a wider assertion: each one hides the race and keeps it.
