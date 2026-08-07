import json
from .config import PLATFORM_DB
from .credentials import decrypt_secret
from .db import connect
from .providers.phase2 import ClickHouseProvider, MySQLProvider, OpenAICompatibleProvider, Phase2ProviderRegistry, RetryPolicy
from .sql_security import SQLPolicy


def public_profile(row) -> dict:
    result=dict(row); result["public_config"]=json.loads(result["public_config"]); result.pop("encrypted_credentials",None); result["credentials_configured"]=True; return result


def build_registry(profile_id: str, require_enabled: bool = True) -> Phase2ProviderRegistry:
    with connect(PLATFORM_DB) as db: row=db.execute("SELECT * FROM phase2_provider_profiles WHERE id=?"+(" AND status='ENABLED'" if require_enabled else ""),(profile_id,)).fetchone()
    if not row: raise ValueError("Phase 2 provider profile is not enabled")
    config=json.loads(row["public_config"]); secret=decrypt_secret(row["encrypted_credentials"])
    retry=RetryPolicy(float(config.get("timeout",30)),int(config.get("retries",2)),float(config.get("backoff",.25)),int(config.get("max_concurrency",4)))
    model=OpenAICompatibleProvider(config["model_base_url"],secret["model_api_key"],config["model"],retry,{"temperature":config.get("model_temperature",.2),"top_p":config.get("model_top_p",.9),"max_tokens":config.get("model_max_tokens",2048),"response_format":{"type":"json_object"}},config.get("model_system_prompt",''))
    policy=SQLPolicy(frozenset(config.get("allowed_tables",[])),int(config.get("max_rows",1000)),int(config.get("max_time_range_days",366)),retry.timeout)
    if row["datasource_type"]=="CLICKHOUSE": datasource=ClickHouseProvider(config["datasource_url"],config["datasource_username"],secret["datasource_password"],config["database"],policy,retry)
    else: datasource=MySQLProvider(config["datasource_host"],int(config.get("datasource_port",3306)),config["datasource_username"],secret["datasource_password"],config["database"],policy,retry,bool(config.get("datasource_tls",True)))
    return Phase2ProviderRegistry(model,datasource,profile_id)
