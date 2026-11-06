# Case Denominator Conservation Gate

Use this gate when generating or updating a non-case-free `api-test-framework/`. Its only purpose is to prevent case IDs from disappearing between the frozen source denominator and generated collection artifacts. It does not replace request, response-binding, confidence, setup/cleanup, SQL, authentication, runtime, or archive-content gates.

## Scope

Conserve IDs across these existing surfaces:

1. Ordinary source denominator: every machine-readable `用例ID` in `执行级接口用例集.md`.
2. Required Flow denominator: every `status: required` `flow_id` in `required_chain_flows.yaml`.
3. Source-bound supplements: H5, billing, runtime-evidence, or other supplemental groups explicitly selected for this framework.
4. Generated structured data: `data/cases/*` and `data/flow_cases.yaml|yml|py`.
5. Collection mapping: `configs/generation_status.yaml.pytest_collection_mapping.mappings`.

Pytest collection and `接口案例.md` remain checked by the existing collection and final-archive gates. Do not reimplement their assertion, marker, confidence, or archive-content rules here.

## Compatibility Boundary

- Existing frameworks without `configs/case_denominator_manifest.yaml` remain valid input. Validate source-subset inclusion, data-to-mapping set equality, and duplicate IDs, but do not fail only because the new manifest is absent.
- Existing `schema_version: 1` manifests keep their original compatibility behavior. New or materially updated frameworks must write `schema_version: 2` and enable upstream-source integrity checks.
- A newly generated or materially updated framework must write the manifest and `generation_status.yaml.case_denominator_conservation` together. Declaring one without the other is a gate failure.
- Case-free or upstream-blocked outputs do not create a manifest.
- `generated_non_live`, `manual_review_only`, and other generated cases may still have collected pytest nodes that skip at runtime. Collection conservation does not promote them into the live execution denominator.
- Optional-async cases stored under their dedicated artifact and collection switch remain governed by the existing optional-async gate. Do not merge them into the default collection denominator here.

## Freeze Before Generation

Before writing case data or pytest files:

1. Parse the execution-level case IDs and required Flow IDs.
2. Inventory every source-bound supplemental group that the framework will include.
3. Record each supplemental group with a stable `group_id`, non-empty `source_refs`, and its complete ordered ID list.
   `source_refs` must point to upstream execution artifacts、source code or normalized runtime evidence. They must not point back to generated `api/`、`configs/`、`core/`、`data/`、`reports/`、`scripts/`、`testcases/` or generated archive documents.
4. Record generated non-default IDs separately for audit; do not use that classification to silently omit their collected node.
5. Freeze the manifest, then generate every downstream surface from this denominator. Do not reconstruct the denominator from generated files after generation.

Use this schema:

```yaml
schema_version: 2
status: passed
source_integrity: upstream_authoritative
ordinary:
  supplemental_groups:
    - group_id: h5-live-supplement
      source_refs:
        - 05-executable-interface-case-set/h5_case_inventory.yaml
      case_ids:
        - EXE-TC-H5-001-MAIN
  non_default_case_ids: []
flows:
  required_source: required_chain_flows
  supplemental_groups:
    - group_id: billing-flow-supplement
      source_refs:
        - 04-runtime-evidence/billing_flow_inventory.yaml
      flow_ids:
        - FLOW-BILLING-001
  non_default_flow_ids: []
```

Empty supplemental groups are valid when the project has no supplemental denominator. Never add placeholder IDs or empty `source_refs`.

For `schema_version: 2`, `source_integrity: upstream_authoritative` is mandatory. A circular reference to an existing Runner、case YAML、generation status or archive is a generation-integrity failure even when all ID counts happen to match. Keep schema version 1 readable only for existing-framework compatibility; do not emit it for new generation.

Use `flows.required_source: required_chain_flows` whenever the upstream denominator exists. A legacy standalone input that genuinely has no `required_chain_flows.yaml` may use `required_source: not_available` only when every generated Flow is frozen in a supplemental group with non-empty source references to its authoritative candidate inventory. Suite runs may not use this exception.

## Exact Release Checks

For each ordinary case ID and Flow ID, require:

- no duplicate within source, supplement, structured data, or pytest mapping;
- every upstream source ID exists in structured generated data;
- structured data IDs and pytest mapping IDs are equal in both directions;
- when the manifest exists, `source IDs ∪ supplemental IDs` equals structured data IDs and pytest mapping IDs in both directions;
- the manifest non-default classification equals the generated data classification;
- existing pytest collection validation proves every mapped node exists and no unmapped node is collected;
- existing final archive validation proves every generated case/Flow has exactly one archive entry.

Any missing, extra, or duplicate ID blocks `case_denominator_conservation.status: passed` and `next_stage_allowed: true`. Report the exact IDs; do not shrink counts to make them agree.

## Status Record

New or materially updated frameworks must add:

```yaml
case_denominator_conservation:
  status: passed
  manifest_path: configs/case_denominator_manifest.yaml
  ordinary_source_count: 0
  ordinary_supplemental_count: 0
  ordinary_generated_count: 0
  flow_source_count: 0
  flow_supplemental_count: 0
  flow_generated_count: 0
  missing_case_ids: []
  extra_case_ids: []
  missing_flow_ids: []
  extra_flow_ids: []
  duplicate_ids: []
```

Counts are summaries only. The ID sets and validator result are authoritative.

## Deterministic Validation

Run after case/Flow data and mapping are final, before pytest collection and final release:

```bash
python3 <skill-dir>/scripts/validate_case_denominator_conservation.py \
  <pipeline-root>/api-test-framework \
  --executable-case-set <pipeline-root>/05-executable-interface-case-set/执行级接口用例集.md \
  --required-chain-flows <pipeline-root>/required_chain_flows.yaml
```

For a suite-bundled component, use the component's own script path. A failure is a generation-integrity defect, not a product or environment defect.
