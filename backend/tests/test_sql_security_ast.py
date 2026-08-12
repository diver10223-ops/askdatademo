import pytest

from app.sql_security import (
    DEFAULT_ANALYTIC_COLUMNS,
    SQLPolicy,
    SQLSecurityError,
    secure_query,
    validate_explain,
)


TABLE = "dws_loan_aggr_wide"


def policy(**changes):
    values = dict(
        allowed_tables=frozenset({TABLE}),
        allowed_columns=DEFAULT_ANALYTIC_COLUMNS,
        max_rows=100,
        max_time_range_days=366,
    )
    values.update(changes)
    return SQLPolicy(**values)


@pytest.mark.parametrize("dialect", ["mysql", "clickhouse"])
def test_ast_supports_dialects_and_enforces_limit(dialect):
    secured = secure_query(
        f"SELECT org_name, loan_cur FROM {TABLE} WHERE stat_dt=:date LIMIT 9999",
        policy(dialect=dialect), {"date": "2026-03-31"},
    )
    assert secured.dialect == dialect and secured.tables == (TABLE,)
    assert secured.sql.endswith("LIMIT 100")


def test_permission_scope_is_parameterized_and_injected_into_each_union_branch():
    sql = f"SELECT org_name FROM {TABLE} WHERE stat_dt=:d1 UNION ALL SELECT org_name FROM {TABLE} WHERE stat_dt=:d2"
    secured = secure_query(sql, policy(), {"d1": "2026-03-31", "d2": "2026-02-28"}, {"orgs": ["上海分行", "北京分行"]})
    assert secured.sql.count("org_name IN") == 2
    assert "北京分行" not in secured.sql and "上海分行" not in secured.sql
    assert secured.parameters["__scope_orgs_0"] == "上海分行" or secured.parameters["__scope_orgs_0"] == "北京分行"
    assert secured.injected_scopes == ("orgs",)


def test_cte_and_nested_query_require_every_physical_branch_to_be_time_bounded():
    safe = f"WITH x AS (SELECT org_name,stat_dt FROM {TABLE} WHERE stat_dt=:date) SELECT org_name FROM x"
    assert "WITH x AS" in secure_query(safe, policy()).sql
    bypass = f"WITH x AS (SELECT org_name FROM {TABLE}) SELECT org_name FROM x WHERE stat_dt=:date"
    with pytest.raises(SQLSecurityError, match="every physical table branch"):
        secure_query(bypass, policy())


@pytest.mark.parametrize("sql", [
    f"SELECT org_name FROM secret.{TABLE} WHERE stat_dt=:date",
    f"SELECT secret_value FROM {TABLE} WHERE stat_dt=:date",
    f"SELECT * FROM {TABLE} WHERE stat_dt=:date",
    f"SELECT org_name FROM {TABLE} WHERE stat_dt=:date UNION SELECT name FROM secret WHERE stat_dt=:date",
])
def test_table_column_schema_and_star_bypasses_are_rejected(sql):
    with pytest.raises(SQLSecurityError):
        secure_query(sql, policy())


@pytest.mark.parametrize("sql", [
    f"DELETE FROM {TABLE} WHERE stat_dt='2026-03-31'",
    f"SELECT org_name FROM {TABLE} WHERE stat_dt='2026-03-31'; SELECT org_name FROM {TABLE} WHERE stat_dt='2026-03-31'",
    f"SELECT sleep(10),org_name FROM {TABLE} WHERE stat_dt='2026-03-31'",
    f"SELECT org_name INTO OUTFILE '/tmp/leak' FROM {TABLE} WHERE stat_dt='2026-03-31'",
    f"SELECT org_name FROM {TABLE} WHERE stat_dt='2026-03-31' FOR UPDATE",
])
def test_write_multi_statement_dangerous_function_and_side_effect_bypasses_are_rejected(sql):
    with pytest.raises(SQLSecurityError):
        secure_query(sql, policy())


def test_time_range_empty_scope_and_complexity_are_final_rejections():
    with pytest.raises(SQLSecurityError, match="time range"):
        secure_query(f"SELECT org_name FROM {TABLE} WHERE stat_dt BETWEEN '2024-01-01' AND '2026-03-31'", policy())
    with pytest.raises(SQLSecurityError, match="empty permission"):
        secure_query(f"SELECT org_name FROM {TABLE} WHERE stat_dt=:date", policy(), permissions={"orgs": []})
    with pytest.raises(SQLSecurityError, match="permission scope is required"):
        secure_query(f"SELECT org_name FROM {TABLE} WHERE stat_dt=:date", policy(require_scope_permissions=True))
    with pytest.raises(SQLSecurityError, match="complexity"):
        secure_query(f"SELECT a.org_name FROM {TABLE} a JOIN {TABLE} b ON a.stat_dt=b.stat_dt WHERE a.stat_dt=:date AND b.stat_dt=:date", policy(max_joins=0))


def test_explain_scan_and_cost_gate():
    assert validate_explain({"estimated_rows": 999, "estimated_cost": 12.5}, policy(max_estimated_scan_rows=1000))["estimated_cost"] == 12.5
    with pytest.raises(SQLSecurityError, match="scan rows"):
        validate_explain({"estimated_rows": 1001, "estimated_cost": 20}, policy(max_estimated_scan_rows=1000))
    with pytest.raises(SQLSecurityError, match="unavailable"):
        validate_explain({}, policy())
