# Splitting Strategy

## 目录

- Core Rule
- Split Priority
- File Size Gate
- Output Layout
- Split Index
- Ordering Rules
- No-Loss Checks
- Naming Rules


Use this reference when generated files may exceed a safe size, or when splitting is requested. The goal is to avoid context overflow while preserving interface completeness.

## Core Rule

Split by complete interface capability, not by arbitrary line count. A split unit must keep together everything needed to understand and run that interface's cases:

- API wrapper methods.
- Main-flow and branch-flow test cases.
- Request data and expected assertion data.
- Token, variable extraction, and injection rules used by the interface.
- API-based precondition and cleanup rules.
- SQL setup/cleanup entries.
- Data model subgraph evidence used by SQL generation.
- Source traceability: case IDs, upstream file references, and gate decisions.

Do not split one interface's happy path, branch path, setup, cleanup, and SQL across unrelated modules without an index that reconnects them.

## Split Priority

Use this order:

1. **Business capability / bounded context**: for example `login`, `order`, `payment`.
2. **Interface group** under the same capability: for example `order_create`, `order_query`, `order_cancel`.
3. **Flow type** only when the interface has many cases and both parts remain complete: `*_main` and `*_branch`.
4. **Case batch** only as a last resort. Keep each batch with its own data, SQL references, and traceability.

Never split by raw table name alone if one interface needs several related tables.

## File Size Gate

Use conservative thresholds:

- Python module target: under 500 lines.
- YAML data file target: under 800 lines.
- SQL command file target: under 800 lines.
- Hard stop: if a single file would exceed roughly 1,200 lines, split it unless doing so breaks interface completeness.

If safe splitting is not possible, block generation and report the reason.

## Output Layout

When splitting is needed, prefer:

```text
api-test-framework/
├── api/
│   ├── login_api.py
│   └── order_api.py
├── testcases/
│   ├── login/
│   │   ├── test_login_main.py
│   │   └── test_login_branch.py
│   └── order/
│       ├── test_order_main.py
│       └── test_order_branch.py
├── data/
│   ├── login.yaml
│   ├── order.yaml
│   └── sql/
│       ├── login_sql_commands.yaml
│       └── order_sql_commands.yaml
└── configs/
    └── split_index.yaml
```

Keep unsplit layout when the files are small.

## Split Index

When any file is split, generate `configs/split_index.yaml`:

```yaml
split_index:
  status: "passed"
  strategy: "interface_complete"
  ordering:
    status: "passed"
    mode: "topological"
    execution_order:
      - "login"
      - "order_create"
      - "order_query"
  modules:
    login:
      sequence: 1
      depends_on: []
      run_after: []
      run_before:
        - "order_create"
      api: "api/login_api.py"
      tests:
        main: "testcases/login/test_login_main.py"
        branch: "testcases/login/test_login_branch.py"
      data: "data/login.yaml"
      sql: "data/sql/login_sql_commands.yaml"
      source_cases:
        - "TC_LOGIN_001"
      data_model_subgraph:
        tables:
          - "user_account"
        relationships:
          - "user_account -> user_profile"
    order_create:
      sequence: 2
      depends_on:
        - "login"
      run_after:
        - "login"
      run_before:
        - "order_query"
      api: "api/order_api.py"
      tests:
        main: "testcases/order/test_order_create_main.py"
        branch: "testcases/order/test_order_create_branch.py"
      data: "data/order_create.yaml"
      sql: "data/sql/order_create_sql_commands.yaml"
      source_cases:
        - "TC_ORDER_001"
      data_model_subgraph:
        tables:
          - "order_main"
          - "order_item"
        relationships:
          - "user_account -> order_main"
          - "order_main -> order_item"
```

The index must let a future agent recover every generated artifact for a single interface without scanning the entire project.

## Ordering Rules

Every split unit must have machine-readable ordering metadata:

- `sequence`: 1-based integer order within the generated project.
- `depends_on`: upstream split units required before this unit can run or be understood.
- `run_after`: execution-order dependency, usually the same as `depends_on` unless a dependency is documentation-only.
- `run_before`: downstream split units that should follow this unit.
- `split_index.ordering.execution_order`: the full ordered list of split unit keys.
- `split_index.ordering.mode`: `source_order` when source case order is sufficient, or `topological` when dependencies require graph ordering.

Build the order from:

- Source document case order.
- Cross-case variable extraction/injection dependencies.
- Token acquisition dependencies.
- API precondition and cleanup dependencies.
- SQL data model graph order.
- Business workflow order when explicitly stated by the source.

If two split units are independent, preserve the order from `执行级接口用例集.md`. If a cycle is found, block generation and report the cycle instead of guessing an order.

## No-Loss Checks

Before marking generation as ready, confirm:

- Every case ID appears in exactly one test module.
- Every generated test maps to exactly one API wrapper.
- Every generated test data entry is referenced by at least one case.
- Every SQL-driven case has exactly one SQL command entry.
- Every SQL file maps to at least one test module and one data model subgraph.
- Every source case in the input appears in the split index.
- Main-flow and branch-flow counts match the source counts.
- Every split unit has `sequence`, `depends_on`, `run_after`, and `run_before`.
- `split_index.ordering.execution_order` contains every split unit exactly once.
- `sequence` values match `execution_order`.
- No dependency cycle exists.

If any check fails, mark the generation as blocked.

## Naming Rules

Use deterministic ASCII-safe names:

- Capability: lowercase snake case, for example `order_payment`.
- API file: `api/<capability>_api.py`.
- Main tests: `testcases/<capability>/test_<capability>_main.py`.
- Branch tests: `testcases/<capability>/test_<capability>_branch.py`.
- Data file: `data/<capability>.yaml`.
- SQL file: `data/sql/<capability>_sql_commands.yaml`.

Keep Chinese labels inside Allure titles and data values when source-bound.
