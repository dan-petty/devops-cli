## ADDED Requirements

### Requirement: A caller override of a key that makes a library or Python load a module is refused
`build_subprocess_env` SHALL raise `SecurityError` for a caller override whose upper-case key starts with `OPENSSL` or `KRB5`, or is `GSS_MECH_CONFIG`, `SASL_PATH`, `PYTHONEXECUTABLE` or `__PYVENV_LAUNCHER__`. The message is "Prohibited dangerous environment variable override: '<key>'" and the error code is `SECURITY_ERROR`. It SHALL do this with environment isolation on and off.

#### Scenario: An OpenSSL configuration file, provider directory or engine directory
- **WHEN** a caller builds a child environment with the override `OPENSSL_CONF`, `OPENSSL_CONF_INCLUDE`, `OPENSSL_MODULES` or `OPENSSL_ENGINES`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: An OpenSSL key that loads no module
- **WHEN** a caller builds a child environment with the override `OPENSSL_SEC_MEM`, `OPENSSL_ia32cap`, `OPENSSL_EXAMPLE_KEY` or `OPENSSL`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A Kerberos key
- **WHEN** a caller builds a child environment with the override `KRB5_CONFIG`, `KRB5_KTNAME`, `KRB5_KDC_PROFILE`, `KRB5_TRACE`, `KRB5CCNAME`, `KRB5_CLIENT_KTNAME` or `KRB5RCACHEDIR`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: The GSS-API mechanism file and the SASL plug-in directory
- **WHEN** a caller builds a child environment with the override `GSS_MECH_CONFIG` or `SASL_PATH`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

#### Scenario: A Python launcher key
- **WHEN** a caller builds a child environment with the override `PYTHONEXECUTABLE` or `__PYVENV_LAUNCHER__`, in upper or lower case
- **THEN** `build_subprocess_env` raises `SecurityError` that names the key, with the error code `SECURITY_ERROR`

### Requirement: A library key that loads no module reaches the child
`build_subprocess_env` SHALL put each key of the caller override that names certificate data, a locale or message directory, a log level or a configuration directory of a library in the child environment with its value. It SHALL do the same for a key that only contains a refused name, or that starts with a refused name with no separator after it.

#### Scenario: Certificate, locale, log and configuration keys, and keys that look like a refused key
- **WHEN** a caller builds a child environment with the overrides `SSL_CERT_FILE`, `SSL_CERT_DIR`, `CURL_CA_BUNDLE`, `CURL_HOME`, `NODE_EXTRA_CA_CERTS`, `LOCPATH`, `NLSPATH`, `GNUTLS_DEBUG_LEVEL`, `P11_KIT_DEBUG`, `SASL_CONF_PATH`, `LDAPCONF`, `EXAMPLE_OPENSSL_CONF`, `EXAMPLE_KRB5_CONFIG`, `GSS_MECH_CONFIGURATION`, `SASL_PATHS` and `PYTHONEXECUTABLES`
- **THEN** the child environment holds each of these keys with its value, with isolation on and off

### Requirement: An isolated child gets no library key from the environment
With environment isolation on, `build_subprocess_env` SHALL keep each key that the previous requirements refuse out of the child environment when the key is in the environment of the process and the caller names no `extra_allowed_keys`.

#### Scenario: Library keys in the environment of the person
- **WHEN** the environment holds `OPENSSL_CONF`, `OPENSSL_MODULES`, `OPENSSL_ENGINES`, `KRB5_CONFIG`, `GSS_MECH_CONFIG`, `SASL_PATH`, `PYTHONEXECUTABLE` and `__PYVENV_LAUNCHER__`, in upper or lower case, and a caller builds a child environment with isolation on
- **THEN** the child environment holds none of these keys

### Requirement: A refused library key starts no child
`run_subprocess` SHALL raise `SecurityError` for a refused key in its `env` argument before it starts the program.

#### Scenario: An OpenSSL configuration in the environment of a program
- **WHEN** a caller runs a program through `run_subprocess` with the override `OPENSSL_CONF`
- **THEN** `run_subprocess` raises `SecurityError`
- **AND** the program does not start
