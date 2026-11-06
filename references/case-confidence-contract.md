# Case Confidence Contract

Use this contract for every generated design case, executable case, ordinary pytest case, optional/non-live case, and E2E flow. Confidence measures evidence completeness and reproducibility. It does not measure whether a scenario is common, important, or expected to succeed.

## Separation Of Concerns

- `confidence_score` answers: how strongly do current facts support this case definition and its claimed result?
- `scenario_relevance` answers: where does this scenario sit in the product journey?
- `assertion_strength` answers: how strongly does the executable assertion observe the business result?
- `automation_decision` answers: whether the case may run live, must stay non-live, or needs manual review.

Never use confidence to replace assertion, setup/cleanup, runtime safety, source conflict, or live-execution gates. A negative case, contract boundary, or confirmed product-defect reproduction may have high confidence when its request, precondition, expected branch, and evidence are complete.

## Required Machine Fields

```yaml
confidence_score: 0.85
confidence_level: medium
confidence_band: scenario_confirmed
confidence_scope: framework
scenario_relevance: contract_boundary
confidence_dimensions:
  contract: 1.0
  request_materialization: 1.0
  scenario_precondition: 0.9
  business_assertion: 0.9
  runtime_repeatability: 0.6
confidence_reason_codes:
  - SOURCE_CONTRACT_CONFIRMED
  - RUNTIME_NOT_VERIFIED
confidence_cap_reasons:
  - RUNTIME_NOT_VERIFIED
confidence_evidence_refs:
  - case_list.yaml#/cases/12
  - execution_fact_sources.yaml#FACT-012
```

Required values:

- `confidence_scope`: `design | executable | framework | design_and_execution`.
- `scenario_relevance`: `core_real_journey | reachable_business_branch | contract_boundary | synthetic_resilience | source_inferred_only`.
- Every dimension is a number from `0` to `1`. At design scope only, execution-only dimensions may be `not_applicable`; applicable weights are then renormalized. Framework cases and flows must use numeric values for all five dimensions.
- `confidence_reason_codes` is a non-empty list of stable uppercase reason codes.
- `confidence_cap_reasons` is an explicit list and may be empty.
- `confidence_evidence_refs` is a non-empty list of source, runtime, DB, API, assertion, setup, cleanup, or archive evidence references. Prose without a resolvable reference is not evidence.

## Deterministic Score

Use these weights:

| Dimension | Weight | Meaning |
|---|---:|---|
| `contract` | 0.25 | Interface, method/path, request/response contract, and source consistency |
| `request_materialization` | 0.20 | Legal concrete input, auth placement, field shape, and variable sources |
| `scenario_precondition` | 0.20 | Role, existing state, setup, uniqueness, time window, and dependency closure |
| `business_assertion` | 0.20 | Business code, key fields, follow-up API/DB observation, and expected branch |
| `runtime_repeatability` | 0.15 | Runtime evidence, requester reuse, deterministic setup, cleanup, and repeatability |

1. Calculate the weighted average over applicable dimensions.
2. Apply the lowest active hard cap.
3. Round down to the nearest `0.05`. Store at most two decimal places.
4. Derive the level and band from the final score; do not author them independently.

Score bands use half-open intervals except the final band:

| Score | `confidence_band` | `confidence_level` | Interpretation |
|---:|---|---|---|
| `[0.00, 0.60)` | `insufficient` | `low` | Contract or materialization evidence is insufficient |
| `[0.60, 0.70)` | `contract_confirmed` | `low` | Interface is credible but request or execution facts remain uncertain |
| `[0.70, 0.80)` | `request_confirmed` | `medium` | Contract and request are credible; scenario state remains uncertain |
| `[0.80, 0.90)` | `scenario_confirmed` | `medium` | Contract, request, scenario, and assertion are credible; runtime closure is incomplete |
| `[0.90, 1.00]` | `runtime_closed` | `high` | The case is evidence-backed and repeatable in its declared execution mode |

## Hard Caps

Apply every matching reason and take the lowest cap:

| `confidence_cap_reasons` value | Maximum score |
|---|---:|
| `SOURCE_CONFLICT_UNRESOLVED` | 0.49 |
| `CONTRACT_NOT_CONFIRMED` | 0.59 |
| `INPUT_NOT_CONFIRMED` | 0.69 |
| `SCENARIO_STATE_NOT_CLOSED` | 0.79 |
| `ASSERTION_BUSINESS_RESULT_NOT_CLOSED` | 0.79 |
| `WRITE_CLEANUP_NOT_MATERIALIZED` | 0.59 |
| `EXTERNAL_DEPENDENCY_SANDBOX_MISSING` | 0.69 |
| `RUNTIME_NOT_VERIFIED` | 0.89 |

If a condition applies, its cap reason must be declared. Clearing a cap requires new evidence and removal of the underlying blocker, not a manual score edit.

## Stage Rules

- Design stage scores contract and scenario evidence. Execution-only dimensions may be `not_applicable` and must not be guessed.
- Executable stage inherits the design evidence, adds request/assertion/setup/cleanup evidence, recalculates the score, and records new evidence refs.
- Framework stage requires all dimensions to be numeric and adds script/runtime/repeatability evidence. It may lower a score when a new conflict appears.
- Treat every stage score as an immutable evidence snapshot for that stage. A downstream observation must not rewrite the upstream score; record and explain the changed score only in the downstream artifact.
- A downstream stage may raise a score only when it adds at least one new evidence reference and a dimension or cap condition actually changes.
- A downstream stage may lower a score only when it adds at least one new evidence reference, a dimension or cap condition actually changes, and the reason-code or cap set explains the newly discovered uncertainty. Lower only the affected dimensions: for example, an unresolved execution precondition changes scenario/runtime evidence, while a confirmed source-contract conflict may change contract evidence. A single unexplained transient failure is not sufficient evidence for a decrease.
- A score change never removes the case, changes its stable ID or traceability mapping, or changes a coverage denominator. Keep confidence separate from `automation_decision`; a lower score may change live eligibility through the existing release gate, but it must not erase design or executable coverage.
- Ordinary cases, error cases, optional async cases, generated non-live cases, and manual-review cases remain in the confidence denominator. Their automation decision does not erase their confidence record.
- Low-confidence cases cannot enter the live pytest denominator. Medium/high confidence does not bypass any existing live, setup/cleanup, assertion-strength, transport, DB, external dependency, or account-state gate.
- `runtime_closed` requires numeric runtime repeatability, no `RUNTIME_NOT_VERIFIED` cap, and live or equivalent deterministic evidence for the declared execution mode. A confirmed product defect may still be `runtime_closed` when the failing result is reproducible and fully evidenced.

## E2E Flow Rule

Every E2E flow has its own confidence object. By default, the flow score is the minimum final confidence score of its ordered steps because the weakest dependency bounds the full journey. A different calculation is allowed only when every step has an independently archived confidence object and the flow records the source-bound aggregation rationale; it may never exceed its weakest required step.

## Human Archive And Tool Projection

Every entry in `接口案例.md` must show only `置信度分数` and `置信度等级` inside that case or flow's own section. Keep band, scope, relevance, dimensions, reason codes, caps, and evidence refs in machine-readable case data and status artifacts for deterministic calculation and audit; do not expand them into the human archive unless the user explicitly requests a diagnostic view. An aggregate confidence table is useful for review but cannot replace per-entry fields, and it should also expose only record identity, score, and level by default. Use one stable `CASE_CONFIDENCE_INLINE:<case-or-flow-id>` block per archived record so deterministic validation can prove inline completeness. If a Postman collection is generated, preserve score and level in the item or folder description without adding non-standard collection schema fields. Generated Allure tests should expose `confidence_score` and `confidence_level` as reporting labels; labels must not alter test execution.

## Release Gate

`configs/generation_status.yaml` must contain `case_confidence_gate` with `status: passed`, candidate and declared counts, high/medium/low counts, and empty `missing_confidence_case_ids`, `invalid_confidence_case_ids`, `low_confidence_live_case_ids`, and `archive_missing_confidence_case_ids`. Counts are derived from generated case and flow data; never hardcode project-specific totals.
