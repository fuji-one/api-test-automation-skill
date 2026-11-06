# Specialized Runner Materialization Contract

Use this contract only when a source-bound case or Flow cannot be represented safely by the shared ordinary-case runner or generic `flow_runner.py`. Typical reasons include protocol streaming, multi-role session switching, bounded DB/ES snapshots, asynchronous observation, or exact restoration that requires one coordinated failure path. Business-domain names are not reasons by themselves.

## Applicability

- No specialized runner marker in generated case or Flow data: record `not_required`; do not create a manifest or add a release blocker.
- A new or materially changed specialized runner: require the complete contract and strict validation.
- An existing targeted patch that does not add, remove, or change a specialized runner: keep the runner outside the patch scope; do not retroactively rewrite it.
- An `all_generated_cases`、cold-start reconstruction, or full reproducibility claim: validate every discovered specialized runner. Legacy unchanged status cannot support that claim.

Use `specialized_runner_id` as the canonical marker. `custom_runner` may be read only as a legacy alias while migrating an existing framework. Newly generated data must not introduce a second dispatch vocabulary.

## Generic-First Decision

Before selecting a specialized runner, prove why the shared runner is insufficient. Prefer these existing mechanisms whenever they can express the behavior without weakening assertions or cleanup:

1. ordinary `steps` with explicit extraction and injection;
2. `data/flow_cases.yaml|py` plus `core/flow_runner.py`;
3. API setup/cleanup fixtures;
4. bounded SQL lifecycle fixtures;
5. shared authentication、transport、runtime-context and assertion utilities.

Do not create a specialized runner merely to hardcode values, bypass a gate, hide login, replace data-driven assertions, or avoid materializing setup/cleanup evidence.

## Upstream Fact Contract

The generation input must contain a source-owned specialized-runner fact, for example `specialized_runner_contracts.yaml`. The exact upstream filename may vary, but it must live outside the generated framework and contain, per runner:

- stable `runner_id`;
- exact consumer case IDs and Flow IDs;
- source-bound reason the generic runner is insufficient;
- ordered business actions and producer/consumer values;
- required roles、authentication and runtime-context inputs;
- result fields and assertion obligations;
- setup、cleanup、restore and final-residue obligations;
- partial-failure behavior and independent cleanup guarantees;
- authoritative source references.

The facts may reference source code、execution-level artifacts、normalized runtime evidence or approved configuration contracts. Generated files are never authoritative input facts.

## Generated Manifest

When applicable, generate `configs/specialized_runner_materialization.yaml` with this shape:

```yaml
schema_version: 1
status: passed
runners:
  - runner_id: wallet_gift_closed_loop
    consumer_case_ids:
      - EXE-TC-GIFT-001
    consumer_flow_ids: []
    reason_generic_runner_insufficient: >-
      需要在同一失败路径内完成双角色登录、钱包快照、异步流水观测和精确恢复
    authoritative_source_refs:
      - ../04-runtime-evidence/gift_runner_contract.yaml#RUNNER-GIFT-001
      - linkyou@commit:wallet-service/src/main/java/example/GiftService.java#present
    adapter:
      module: core.gift_closed_loop
      callable: run_specialized
    generation_contract:
      inputs:
        - definition
        - client
        - env_config
        - runtime_context
        - auth_contexts
      ordered_actions:
        - 双角色认证并确认账号上下文
        - 快照发送方和接收方钱包
        - 发送当前轮唯一标识的礼物请求
        - 观测当前轮流水和余额变化
      result_fields:
        - gift_business_code
        - restore
      assertion_obligations:
        - 业务码和当前轮流水一致
        - 钱包变化符合源码公式
      cleanup_guarantees:
        - 按当前轮业务号精确删除流水
        - 按完整快照恢复钱包并校验零残留
      failure_path_guarantees:
        - 任一步骤失败后仍尝试全部独立恢复动作
    generated_files:
      - core/gift_closed_loop.py
```

Rules:

- `runner_id` must equal the marker in generated case/Flow data.
- Consumer sets must equal the discovered case/Flow sets in both directions.
- `authoritative_source_refs` must be non-empty and must not point to generated surfaces under the framework, including `api/`、`configs/`、`core/`、`data/`、`reports/`、`scripts/`、`testcases/` or generated archive documents.
- `adapter.module` must be a `core.*` module and `adapter.callable` must exist in that module.
- Every adapter exposes the same keyword contract:

```python
def run_specialized(
    *,
    definition,
    client,
    env_config,
    runtime_context,
    auth_contexts,
):
    ...
```

- The adapter returns a dictionary. Shared dispatch validates declarative result assertions; the implementation may add stronger source-bound assertions, but may not weaken or skip declared obligations.
- `generated_files` must use framework-relative paths, must exist, and must include the adapter implementation file.
- Generated Python keeps business code inside `core/`; pytest entrypoints remain thin and use the shared specialized-runner dispatcher.
- Specialized runners reuse the shared client、authentication registry、runtime context、database engines and transport policy. They must not create a second incompatible requester or hidden secret source.

When applicable, mirror the gate summary in `configs/generation_status.yaml`:

```yaml
specialized_runner_materialization:
  status: passed
  manifest_path: configs/specialized_runner_materialization.yaml
  runner_count: 1
  consumer_case_count: 1
  consumer_flow_count: 0
  errors: []
```

Counts are summaries. Runner and consumer set equality remains authoritative.

## Declarative Result Assertions

Generated case data may use `specialized_runner_assertions` with these generic operations:

```yaml
specialized_runner_assertions:
  equals:
    gift_business_code: 200
  true_fields:
    - login_success
  required_fields:
    - restore
  all_true_fields:
    - restore
```

Paths are dotted dictionary paths. Do not encode business-specific assertion functions in `test_api_cases.py`. If the declarative result is insufficient, keep the stronger assertion inside the specialized implementation and list it under `assertion_obligations`.

## Cold-Start Reproduction

For a full reproducibility claim:

1. Create a fresh temporary framework directory from the template.
2. Re-read authoritative upstream artifacts; do not copy `core/`、`data/`、`configs/` or pytest files from the existing generated framework.
3. Generate the frozen case/Flow denominator and specialized-runner manifest before generating implementation files.
4. Generate all ordinary data、Flow data、adapters and specialized implementations.
5. Run the specialized-runner validator against the fresh framework and compare it with the reviewed baseline using `--rebuilt-framework`.
6. Run denominator conservation、Python compilation、pytest collection、flow semantics and every other applicable release gate against the fresh framework.
7. Delete the temporary framework after recording the machine-readable results.

The comparison is semantic, not byte-for-byte. Require equality of runner IDs、consumer IDs、adapter locations、source facts、generation obligations and generated-file surfaces. Formatting、comment wording and implementation-local refactoring may differ when behavior and contracts remain equivalent.

## Validation Command

```bash
python3 <skill-dir>/scripts/validate_specialized_runner_materialization.py \
  <pipeline-root>/api-test-framework
```

For cold-start comparison:

```bash
python3 <skill-dir>/scripts/validate_specialized_runner_materialization.py \
  <reviewed-framework> \
  --rebuilt-framework <fresh-temporary-framework>
```

A failure is a script-generation integrity defect. Do not classify it as a product defect or repair it by removing consumers from the denominator.
