import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping

from sqlglot import exp, parse
from sqlglot.errors import ParseError


class SQLSecurityError(ValueError):
    pass


DEFAULT_ANALYTIC_COLUMNS = frozenset({
    "org_name", "stat_dt", "loan_cur", "loan_last", "retail_cur", "retail_last",
    "corporate_cur", "corporate_last", "current_value", "previous_value", "factor", "contribution",
})


@dataclass(frozen=True)
class SQLPolicy:
    allowed_tables: frozenset[str]
    max_rows: int = 1000
    max_time_range_days: int = 366
    timeout_seconds: float = 30.0
    dialect: str = "mysql"
    allowed_columns: frozenset[str] = field(default_factory=frozenset)
    time_columns: frozenset[str] = field(default_factory=lambda: frozenset({"stat_dt", "event_date", "created_at", "updated_at", "biz_date"}))
    scope_columns: Mapping[str, str] = field(default_factory=lambda: {"orgs": "org_name"})
    max_ast_nodes: int = 300
    max_joins: int = 4
    max_subqueries: int = 4
    max_estimated_scan_rows: int = 1_000_000
    allow_star: bool = False
    explain_required: bool = True
    require_scope_permissions: bool = False


@dataclass(frozen=True)
class SecuredQuery:
    sql: str
    parameters: dict[str, Any]
    dialect: str
    tables: tuple[str, ...]
    columns: tuple[str, ...]
    injected_scopes: tuple[str, ...]
    ast_nodes: int
    joins: int
    subqueries: int
    max_rows: int


_DIALECTS = {"mysql", "clickhouse"}
_FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter,
    exp.Command, exp.Merge, exp.Transaction, exp.Commit, exp.Rollback,
    exp.Into, exp.Lock,
)
_DENIED_FUNCTIONS = {"sleep", "sleepEachRow", "benchmark", "file", "url", "remote", "remoteSecure", "mysql", "postgresql", "odbc", "jdbc", "hdfs", "s3"}
_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")


def _name(value: str) -> str:
    return value.strip('`"[]').lower()


def _table_name(table: exp.Table) -> str:
    return ".".join(_name(value) for value in (table.catalog, table.db, table.name) if value)


def _physical_tables(tree: exp.Expression) -> set[str]:
    ctes = {_name(cte.alias_or_name) for cte in tree.find_all(exp.CTE)}
    return {_table_name(table) for table in tree.find_all(exp.Table) if _name(table.name) not in ctes}


def _direct_physical_tables(select: exp.Select, ctes: set[str]) -> list[exp.Table]:
    return [table for table in select.find_all(exp.Table) if table.find_ancestor(exp.Select) is select and _name(table.name) not in ctes]


def _validate_time_bound(tree: exp.Expression, policy: SQLPolicy) -> None:
    time_columns = {_name(value) for value in policy.time_columns}
    ctes = {_name(cte.alias_or_name) for cte in tree.find_all(exp.CTE)}
    for select in tree.find_all(exp.Select):
        if not _direct_physical_tables(select, ctes):
            continue
        predicates = [predicate for predicate in select.find_all(exp.Predicate) if predicate.find_ancestor(exp.Select) is select]
        bounded = any(isinstance(predicate, (exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Between)) and any(_name(column.name) in time_columns for column in predicate.find_all(exp.Column)) for predicate in predicates)
        if not bounded:
            raise SQLSecurityError("every physical table branch requires a bounded time predicate")
    dates = [date(*map(int, match.groups())) for match in _DATE.finditer(tree.sql())]
    if len(dates) >= 2 and (max(dates) - min(dates)).days > policy.max_time_range_days:
        raise SQLSecurityError("time range exceeds policy")


def _inject_scopes(tree: exp.Expression, policy: SQLPolicy, permissions: Mapping[str, Any], parameters: dict[str, Any]) -> tuple[str, ...]:
    injected = []
    ctes = {_name(cte.alias_or_name) for cte in tree.find_all(exp.CTE)}
    for permission_key, column in policy.scope_columns.items():
        if permission_key not in permissions:
            if policy.require_scope_permissions:
                raise SQLSecurityError(f"permission scope is required: {permission_key}")
            continue
        values = permissions.get(permission_key)
        if not isinstance(values, (list, tuple, set, frozenset)) or not values:
            raise SQLSecurityError(f"empty permission scope: {permission_key}")
        placeholders = []
        for index, value in enumerate(sorted({str(item) for item in values})):
            key = f"__scope_{permission_key}_{index}"
            parameters[key] = value
            placeholders.append(f":{key}")
        for select in list(tree.find_all(exp.Select)):
            physical = _direct_physical_tables(select, ctes)
            if not physical:
                continue
            conditions=[]
            for table in physical:
                qualifier=table.alias_or_name
                conditions.append(f"{qualifier}.{column} IN ({','.join(placeholders)})")
            condition=parse(f"SELECT 1 WHERE {' AND '.join(conditions)}",read="mysql")[0].args["where"].this
            updated=select.where(condition,append=True)
            if select is tree: tree.args.update(updated.args)
            else: select.replace(updated)
        injected.append(permission_key)
    return tuple(injected)


def secure_query(sql: str, policy: SQLPolicy, parameters: Mapping[str, Any] | None = None, permissions: Mapping[str, Any] | None = None) -> SecuredQuery:
    dialect = policy.dialect.lower()
    if dialect not in _DIALECTS:
        raise SQLSecurityError(f"unsupported dialect: {dialect}")
    try:
        statements = parse(sql, read=dialect)
    except (ParseError, ValueError) as exc:
        raise SQLSecurityError("SQL parse failed") from exc
    if len(statements) != 1 or statements[0] is None:
        raise SQLSecurityError("exactly one statement is required")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SQLSecurityError("only SELECT or CTE query is allowed")
    forbidden = next((node for node in tree.walk() if isinstance(node, _FORBIDDEN_NODES)), None)
    if forbidden is not None:
        raise SQLSecurityError(f"forbidden SQL node: {type(forbidden).__name__}")
    functions = {(function.name if isinstance(function, exp.Anonymous) else function.sql_name()).lower() for function in tree.find_all(exp.Func)}
    if functions & {value.lower() for value in _DENIED_FUNCTIONS}:
        raise SQLSecurityError(f"dangerous function is forbidden: {sorted(functions & {value.lower() for value in _DENIED_FUNCTIONS})}")

    nodes = sum(1 for _ in tree.walk())
    joins = sum(1 for _ in tree.find_all(exp.Join))
    subqueries = sum(1 for _ in tree.find_all(exp.Subquery))
    if nodes > policy.max_ast_nodes or joins > policy.max_joins or subqueries > policy.max_subqueries:
        raise SQLSecurityError("query complexity exceeds policy")

    tables = _physical_tables(tree)
    allowed_tables = {_name(value) for value in policy.allowed_tables}
    if not tables or not tables <= allowed_tables:
        raise SQLSecurityError(f"table is not allowed: {sorted(tables - allowed_tables)}")

    columns = {_name(column.name) for column in tree.find_all(exp.Column)}
    stars = list(tree.find_all(exp.Star))
    if stars and not policy.allow_star:
        raise SQLSecurityError("star projection is forbidden")
    if not policy.allowed_columns:
        raise SQLSecurityError("column whitelist is required")
    allowed_columns = {_name(value) for value in policy.allowed_columns} | {_name(value) for value in policy.time_columns} | {_name(value) for value in policy.scope_columns.values()}
    if not columns <= allowed_columns:
        raise SQLSecurityError(f"column is not allowed: {sorted(columns - allowed_columns)}")
    _validate_time_bound(tree, policy)

    secured_parameters = dict(parameters or {})
    injected = _inject_scopes(tree, policy, permissions or {}, secured_parameters)
    limit = tree.args.get("limit")
    limit_value = limit.expression if limit is not None else None
    if not isinstance(limit_value, exp.Literal) or not limit_value.is_int or int(limit_value.this) > policy.max_rows:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(policy.max_rows)))
    rendered = tree.sql(dialect=dialect)
    if dialect == "clickhouse":
        rendered = re.sub(r"\{([A-Za-z_]\w*):\s*\}", r":\1", rendered)
    return SecuredQuery(rendered, secured_parameters, dialect, tuple(sorted(tables)), tuple(sorted(columns)), injected, nodes, joins, subqueries, policy.max_rows)


def secure_sql(sql: str, policy: SQLPolicy) -> str:
    return secure_query(sql, policy).sql


def validate_explain(explain: Mapping[str, Any], policy: SQLPolicy) -> dict[str, float]:
    try:
        estimated_rows = int(explain["estimated_rows"])
        estimated_cost = float(explain.get("estimated_cost", estimated_rows))
    except (KeyError, TypeError, ValueError) as exc:
        raise SQLSecurityError("EXPLAIN estimate is unavailable") from exc
    if estimated_rows < 0 or estimated_rows > policy.max_estimated_scan_rows:
        raise SQLSecurityError("estimated scan rows exceed policy")
    return {"estimated_rows": estimated_rows, "estimated_cost": estimated_cost}
