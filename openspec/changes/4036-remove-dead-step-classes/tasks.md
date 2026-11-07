# Tasks

## 1. Remove the dead step classes

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`, `k8s/devops/configmap.example.yaml`. Changes: the same four files, `tests/roadmap/implement/test_roadmap_implement_step_classes.py` and `tests/config/test_settings.py`.

- [x] 1.1 Write the failing tests in `tests/roadmap/implement/test_roadmap_implement_step_classes.py`: `StepClass` has exactly `EDIT` and `REPAIR`; the constant, the default ladder and the example ConfigMap ladder hold exactly `edit` and `repair`; a ladder with the key `plan` or `review` is refused with a message; the description of the setting names the two classes. Change the two ladder tests of `tests/config/test_settings.py` to the keys `edit` and `repair`. On the base the new tests fail because the four classes exist.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_classes.py tests/config/test_settings.py`
- [x] 1.2 Remove `PLAN` and `REVIEW` from `StepClass` and from its docstring. Remove `plan` and `review` from `CONST_ROADMAP_IMPLEMENT_STEP_CLASSES` and from the comment above it. Change the description of `roadmap.implement.ladder`. Remove the keys `plan` and `review` from the ladder in `k8s/devops/configmap.example.yaml`.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_classes.py tests/config/test_settings.py tests/config/test_k8s_devops_runtime.py`
- [x] 1.3 Check that no code or test names the removed classes.
  - Verification: `$ ! git grep -n -F StepClass.PLAN src/ tests/` `$ ! git grep -n -F StepClass.REVIEW src/ tests/`

## 2. Fix the documents that name the old classes

Kind: documents. Changes: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `docs/roadmap/implement.md`, `k8s/README.md`.

- [x] 2.1 Regenerate `docs/ENV_VARS.md` and `docs/CONFIGURATION.md`. Fix each text in `docs/roadmap/implement.md` and `k8s/README.md` that names the classes `plan` or `review`.
  - Verification: `$ uv run devops docs generate --check`
- [x] 2.2 Check the specs and the change.
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: remove the keys `plan` and `review` from `roadmap.implement.ladder` in the live ConfigMap `devops-cli-config` in the same deploy. The validator refuses a ladder key that is not a step class. Show the diff first. This change applies nothing to the cluster.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
