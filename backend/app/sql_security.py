import re
from dataclasses import dataclass
from datetime import date


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
_CTE = re.compile(r"(?:^|,)\s*([a-z_]\w*)\s+as\s*\(", re.I)
_TIME = re.compile(r"\b(stat_dt|event_date|created_at|updated_at|biz_date)\b\s*(=|between|>=|>)", re.I)
_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")


def secure_sql(sql: str, policy: SQLPolicy) -> str:
    normalized = re.sub(r"/\*.*?\*/|--[^\n]*", " ", sql, flags=re.S).strip()
    if not normalized or not re.match(r"^(select|with)\b", normalized, re.I):
        raise SQLSecurityError("only SELECT or CTE is allowed")
    if ";" in normalized.rstrip(";"):
        raise SQLSecurityError("multiple statements are forbidden")
    if _BLOCKED.search(normalized):
        raise SQLSecurityError("DDL/DML is forbidden")
    aliases={m.group(1).lower() for m in _CTE.finditer(normalized)}
    tables = {m.group(1).strip('`"[]').lower() for m in _TABLE.finditer(normalized)}-aliases
    allowed = {x.lower() for x in policy.allowed_tables}
    if not tables or not tables <= allowed:
        raise SQLSecurityError(f"table is not allowed: {sorted(tables - allowed)}")
    if not _TIME.search(normalized): raise SQLSecurityError("bounded time predicate is required")
    dates=[date(*map(int,m.groups())) for m in _DATE.finditer(normalized)]
    if len(dates)>=2 and (max(dates)-min(dates)).days>policy.max_time_range_days: raise SQLSecurityError("time range exceeds policy")
    limit=re.search(r"\blimit\s+(\d+)\b",normalized,re.I)
    if limit and int(limit.group(1))>policy.max_rows: normalized=normalized[:limit.start(1)]+str(policy.max_rows)+normalized[limit.end(1):]
    elif not limit:
        normalized = f"{normalized.rstrip(';')} LIMIT {policy.max_rows}"
    return normalized
