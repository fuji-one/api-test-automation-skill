# Unified Runtime Configuration Entry

## Purpose

Provide one clear operator-facing place to enter local runtime accounts, endpoints, and secrets without flattening the framework's internal environment, authentication, database, or transport configuration.

## Applicability

Apply this contract when local execution requires operator-supplied values from multiple files or from multiple categories such as accounts, databases, middleware, gateways, or secrets. Also apply it when the user explicitly asks for one configuration form.

Do not add a new form when the project already has one authoritative secure entrypoint, such as a CI secret store, Vault integration, platform-managed runtime configuration, or one established local config file. Do not require a unified document for projects with no operator-supplied runtime values.

For human-operated local projects, prefer a root-level Markdown form with instructions and one machine-readable bounded block. Follow an established project format instead when it already provides equally clear editing and deterministic parsing. This artifact is an operational input, not standalone project documentation.

## Generation Contract

- Derive field names, account roles, expected identities, endpoints, and required services from project evidence. Never copy product-specific identifiers or addresses from another project.
- Generate placeholders only. Do not invent, infer, or embed real passwords, tokens, private keys, verification codes, or connection secrets.
- Explain prerequisites, target environment, value format, account/role meaning, preflight command, and run command next to the form.
- Keep one uniquely bounded machine-readable block. Parse the first `=` only so secret values may contain `=`. Reject duplicate keys, unknown keys, missing keys, unfilled placeholders, malformed encoding, and invalid source-bound identity/format constraints before any network request.
- Map form values into the existing internal configuration contract, such as `configs/{env}.yaml`, `configs/database.yaml`, runtime variables, and authentication fixtures. Do not replace those internal layers with document parsing inside business tests.
- Make the standard entrypoint read only the declared authoritative local source. Do not silently fall back among a unified form, legacy account documents, shell profiles, old secret files, or cached values.
- Keep configuration readiness separate from execution authorization. Completing the form must not unskip non-live cases or authorize irreversible notifications, financial mutations, destructive operations, or production execution.

## Security Contract

- Mark a filled local form as sensitive, exclude it from version control, and restrict it to the current user where the operating system supports file permissions.
- Never print form values, parsed dictionaries, connection URLs containing credentials, tokens, or secret-bearing exceptions. Include every injected sensitive value in report/log redaction.
- Keep tokens and session secrets in memory unless a confirmed secure store is the authoritative source.
- Record only field names, readiness state, source path, and redacted validation results in status artifacts.
- Store the standardized metadata below in `configs/generation_status.yaml` when the capability is used:

```yaml
runtime_usability:
  runtime_configuration_entry:
    status: provided | pending_values | not_required
    mode: unified_local_document | established_secure_source | not_required
    authoritative_source: ""
    local_sensitive_files: []
    preflight_command: ""
    legacy_sources_disabled: true
    version_control_excluded: true
```

Use empty `local_sensitive_files` for CI/Vault/platform-managed sources. Do not store secret values in this metadata.

## Preflight And Validation

The no-network preflight must validate the form and runtime dependencies before pytest or live requests. Test at least:

- complete valid input;
- missing, placeholder, duplicate, and unknown fields;
- secret values containing `=` and URL-reserved characters;
- role/account identity mismatch when the source contract fixes identity;
- dependency and system-command checks;
- sensitive-value redaction;
- version-control exclusion and, when applicable, user-only file permissions;
- standard entrypoint use of the single source with legacy fallback disabled;
- actual-run-path synchronization and pytest collection after copying a runnable framework.

Treat missing runtime values as `pending_values` rather than a script-generation defect when the template, parser, preflight, and internal mappings are complete. Treat parser/config mismatch, silent fallback, missing redaction, or an uploadable filled form as a generator defect.
