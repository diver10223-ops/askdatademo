import re
from dataclasses import dataclass


class SQLSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class SQLPolicy:
    allowed_tables: frozenset[str]
    max_rows: int = 1000
    max_time_range_days: int = 366
    timeout_seconds: float = 30.0


_BLOCKED = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|attach|detach|call|execute|merge)\b", re.I)
_TABLE = re.compile(r"\b(?:from|join)\s+([`\"\[]?[\w.]+[`\"\]]?)", re.I)


def secure_sql(sql: str, policy: SQLPolicy) -> str:
    normalized = re.sub(r"/\*.*?\*/|--[^\n]*", " ", sql, flags=re.S).strip()
    if not normalized or not re.match(r"^(select|with)\b", normalized, re.I):
        raise SQLSecurityError("only SELECT or CTE is allowed")
    if ";" in normalized.rstrip(";"):
        raise SQLSecurityError("multiple statements are forbidden")
    if _BLOCKED.search(normalized):
        raise SQLSecurityError("DDL/DML is forbidden")
    tables = {m.group(1).strip('`"[]').lower() for m in _TABLE.finditer(normalized)}
    allowed = {x.lower() for x in policy.allowed_tables}
    if not tables or not tables <= allowed:
        raise SQLSecurityError(f"table is not allowed: {sorted(tables - allowed)}")
    if not re.search(r"\blimit\s+\d+\b", normalized, re.I):
        normalized = f"{normalized.rstrip(';')} LIMIT {policy.max_rows}"
    return normalized
