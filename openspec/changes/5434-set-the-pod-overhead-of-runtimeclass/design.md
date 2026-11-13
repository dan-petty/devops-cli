# Design

## Decisions

- **Memory `16Mi`, rounded up from the measured 15.1 MiB.** Under `runc`, the pod working set minus the RSS of the container was -7.7 MiB. Under `runsc`, it was +7.4 MiB. The difference, 15.1 MiB, is the fixed memory of the sandbox (the Sentry and the gofer) in each pod. A value rounded up keeps the scheduler and the quota on the safe side.
- **No `cpu` key.** The CPU task took 1.4 s in both arms, so the measurement found no CPU overhead. A `cpu` value with no measurement would be a guess.
- **The test pins the whole `overhead` object.** An equality on `{"podFixed": {"memory": "16Mi"}}` fails when the value changes and also when a `cpu` key appears. A new value needs a new measurement and a change of the test.
- **The header comment names the source of the value.** The line that blocked each workload until #5434 is now wrong, so it goes. The replacement lines give the measured value and the issue, so a reader of the file finds the evidence.
- **No workload moves to the class.** The measurement shows that the class is usable. The first workload is a sandbox entry under #5447 that the owner approves.

## Rejected alternatives

- **Memory `15Mi`.** It is below the measured 15.1 MiB, so each pod would hold more memory than the scheduler counts.
- **A larger margin, such as `32Mi` or `64Mi`.** The memory test held 512 MiB for 60 s in 3 runs, and the overhead stayed near 7.4 MiB above the RSS. No measurement shows a growth that a larger value must cover. A larger value only takes schedulable memory from the node.
- **A `cpu` overhead such as `50m`.** The CPU arm of the measurement shows no overhead (1.4 s in both arms), so no evidence supports a value.
