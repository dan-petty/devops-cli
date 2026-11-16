# Tasks

## 1. The class of an evicted pod

- [x] 1.1 Write failing tests: a pod with the reason `Evicted`, the message of a volume over its limit and the exit status 137 gives `limit_reached`, a node low on a resource gives `ci_infra`, and the exit status 137 is `oom` only with the container reason `OOMKilled` or with no container reason
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py`
- [x] 1.2 Add the reason of the container and the reason and the message of the pod to `FailureEvidence`, and classify an eviction before the exit status
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py`
- [x] 1.3 Write failing tests: `ClusterJobs.pod_end` reads the exit status, the reason of the container and the reason and the message of the pod, and the report of an evicted runner Job records `limit_reached` and quotes the message
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 1.4 Replace `ClusterJobs.exit_status` with `pod_end`, give its fields to the classifier, and add the message of the kubelet to the report
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_cluster_job_api.py tests/roadmap/implement/test_roadmap_implement_submit.py`

## 2. The space of the strength check

- [x] 2.1 Write a failing test: the mutation run sets `only_mutate` to the files of its targets for `mutmut run` and `mutmut results`, and removes `mutants/` after it
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py`
- [x] 2.2 Set `only_mutate` in the mutmut table of the run, read the results in the same block, and remove the tree in a `finally`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_strength.py`

## 3. The runner volume

- [x] 3.1 Change the gate checks to a home volume of 8 Gi and `ephemeral-storage` of 4 Gi requested and 10 Gi at most, and see them fail
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 3.2 Set the values in `k8s/devops/cronjob-runner.yaml` with the measured sizes in its comments
  - Verification: `$ uv run devops ci --check --only k8s`

## 4. Documents

- [x] 4.1 Change the runner template and the classes of a stop `job` in `docs/CLUSTER.md`, and the mutation run in `docs/roadmap/implement.md`
  - Verification: `$ uv run devops ci docs`

- Pending a person: after the deploy, a runner Job that reaches the strength check ends with no eviction, and `kubectl -n devops get cronjob devops-cli-runner -o jsonpath='{.spec.jobTemplate.spec.template.spec.volumes[1].emptyDir.sizeLimit}'` prints `8Gi`.
