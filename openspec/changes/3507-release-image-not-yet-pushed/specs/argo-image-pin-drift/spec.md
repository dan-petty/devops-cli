## MODIFIED Requirements

### Requirement: The registry read is anonymous and public
The registry read SHALL use the project's egress-checked HTTP client at the public level, answer a 401 Bearer challenge with an anonymous token from the challenge's realm, and raise `RegistryReadError` (`DOCKER_REGISTRY_READ_ERROR`) when the registry gives no anonymous token, no manifest for the tag for a status other than 404, or no `Docker-Content-Digest`. When the registry answers HTTP 404 for the tag, the read SHALL raise `RegistryTagNotFoundError` (`DOCKER_REGISTRY_TAG_NOT_FOUND`), a subclass of `RegistryReadError`, so a caller that catches `RegistryReadError` also catches a missing tag.

#### Scenario: A registry that refuses anonymous pulls
- **WHEN** the token endpoint of the registry answers 401
- **THEN** the read raises `RegistryReadError` that says the image needs credentials, and the status panel reports the pin as not read and the command exits 1

#### Scenario: A pin whose tag the registry does not hold
- **WHEN** the registry answers HTTP 404 for the tag of a pin
- **THEN** the read raises `RegistryTagNotFoundError`, the status panel reports the pin as not read with the message of the error, and no exception escapes
