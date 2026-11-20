## ADDED Requirements

### Requirement: The scaffolded devcontainer adds no Feature
The `devcontainer.json` that `devops devcontainer init` writes SHALL have no `features` key, with the published image and with an image that `--image` names. The image SHALL supply the user `vscode` and the tools. `--minikube` SHALL add only the forwarded ports of the Minikube stack.

#### Scenario: An image that --image names gets no Feature
- **WHEN** a test runs `devops devcontainer init --image python:3.14` in an empty directory
- **THEN** the written `devcontainer.json` has the image `python:3.14` and no `features` key

#### Scenario: The published image gets no Feature
- **WHEN** a test runs `devops devcontainer init --published` in an empty directory
- **THEN** the written `devcontainer.json` has the published image and no `features` key

#### Scenario: --minikube adds only the forwarded ports
- **WHEN** a test renders `devcontainer.json.j2` with `minikube` true and then with `minikube` false
- **THEN** the first output has `forwardPorts`, the second has no `forwardPorts`, and neither output has a `features` key
