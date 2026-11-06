"""Verify that every possible mutation row is bound to declared ownership keys."""
from typing import Any


def validate_ownership_sql(sql: str, command: dict[str, Any], params: dict[str, Any]) -> None:
    import sqlglot
    from sqlglot import exp

    try:
        statements = sqlglot.parse(sql, read=command.get("sql_dialect", "mysql"))
    except sqlglot.errors.ParseError:
        raise ValueError("SQL 归属边界无法解析，禁止执行写操作") from None
    if len(statements) != 1 or not isinstance(statements[0], (exp.Update, exp.Delete)):
        raise ValueError("SQL 归属边界必须是单条 UPDATE/DELETE")
    tree = statements[0]
    target = tree.this
    if not isinstance(target, exp.Table) or target.args.get("joins") or tree.args.get("tables"):
        raise ValueError("多目标表写操作不能证明单表归属边界")
    ownership = command.get("ownership") or {}
    keys = ownership.get("keys") or []
    if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or not k.isidentifier() for k in keys):
        raise ValueError("UPDATE/DELETE 必须声明精确的 ownership.keys")
    where = tree.args.get("where")
    if where is None:
        raise ValueError("UPDATE/DELETE 缺少 WHERE 归属边界")
    target_names = {target.name.lower(), target.alias_or_name.lower()}

    def anchors(node: exp.Expression) -> set[str]:
        if isinstance(node, exp.Paren):
            return anchors(node.this)
        if isinstance(node, exp.And):
            return anchors(node.this) | anchors(node.expression)
        if isinstance(node, exp.Or):
            return anchors(node.this) & anchors(node.expression)
        if isinstance(node, exp.EQ):
            for column, placeholder in ((node.this, node.expression), (node.expression, node.this)):
                if not isinstance(column, exp.Column) or not isinstance(placeholder, exp.Placeholder):
                    continue
                if column.table and column.table.lower() not in target_names:
                    continue
                name = str(placeholder.this)
                value = params.get(name)
                if value is None or value == "" or isinstance(value, (dict, list, tuple, set)):
                    continue
                return {column.name.lower()}
        return set()

    missing = {key.lower() for key in keys} - anchors(where.this)
    if missing:
        raise ValueError("WHERE 每个分支都必须用绑定参数等值限定归属键：" + ", ".join(sorted(missing)))
