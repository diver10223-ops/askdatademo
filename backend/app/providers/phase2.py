import asyncio
import base64
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ..sql_security import SQLPolicy, secure_sql


@dataclass
class RetryPolicy:
    timeout: float = 30.0
    retries: int = 2
    backoff: float = 0.25
    max_concurrency: int = 4


class AsyncGate:
    def __init__(self, policy: RetryPolicy): self.policy, self.gate = policy, asyncio.Semaphore(policy.max_concurrency)
    async def run(self, operation):
        async with self.gate:
            for attempt in range(self.policy.retries + 1):
                try: return await asyncio.wait_for(asyncio.to_thread(operation), self.policy.timeout)
                except (TimeoutError, urllib.error.URLError, OSError):
                    if attempt == self.policy.retries: raise
                    await asyncio.sleep(self.policy.backoff * (2 ** attempt))


def network_diagnostics(host: str, port: int, use_tls: bool, timeout: float = 5.0) -> dict:
    started=time.perf_counter(); result={"dns":False,"tcp":False,"tls":False,"host":host,"port":port}
    addresses=socket.getaddrinfo(host, port, type=socket.SOCK_STREAM); result["dns"]=bool(addresses)
    with socket.create_connection((host, port), timeout=timeout) as raw:
        result["tcp"]=True
        if use_tls:
            with ssl.create_default_context().wrap_socket(raw, server_hostname=host): result["tls"]=True
    result["elapsed_ms"]=(time.perf_counter()-started)*1000; return result


@dataclass
class OpenAICompatibleProvider:
    base_url: str
    api_key: str
    model: str
    policy: RetryPolicy = field(default_factory=RetryPolicy)
    capabilities: dict = field(default_factory=lambda:{"structured_output":True,"tasks":["L2","L7"]})
    def __post_init__(self): self.runner=AsyncGate(self.policy)
    async def health_check(self):
        url=self.base_url.rstrip('/')+'/models'
        def call():
            request=urllib.request.Request(url,headers={"Authorization":f"Bearer {self.api_key}"})
            with urllib.request.urlopen(request,timeout=self.policy.timeout) as response: return response.status
        status=await self.runner.run(call); return {"status":"READY" if status<400 else "FAILED","provider":"OPENAI_COMPATIBLE","network":True}
    async def structured_generate(self, task: str, payload: dict):
        body=json.dumps({"model":self.model,"messages":[{"role":"system","content":f"Return JSON for NLQ {task}."},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],"response_format":{"type":"json_object"}},ensure_ascii=False).encode()
        def call():
            request=urllib.request.Request(self.base_url.rstrip('/')+'/chat/completions',data=body,method='POST',headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"})
            with urllib.request.urlopen(request,timeout=self.policy.timeout) as response: return json.loads(response.read())
        response=await self.runner.run(call); content=response["choices"][0]["message"]["content"]
        return json.loads(content) if isinstance(content,str) else content


@dataclass
class ClickHouseProvider:
    url: str; username: str; password: str; database: str; sql_policy: SQLPolicy; policy: RetryPolicy = field(default_factory=RetryPolicy)
    def __post_init__(self): self.runner=AsyncGate(self.policy)
    async def health_check(self):
        def call():
            request=urllib.request.Request(self.url.rstrip('/')+'/?query=SELECT%201')
            request.add_header('Authorization','Basic '+base64.b64encode(f'{self.username}:{self.password}'.encode()).decode())
            with urllib.request.urlopen(request,timeout=self.policy.timeout) as response: return response.read().decode().strip()
        value=await self.runner.run(call); return {"status":"READY" if value=='1' else "FAILED","provider":"CLICKHOUSE","network":True}
    async def execute(self, sql: str, parameters: dict) -> list[dict[str,Any]]:
        safe=secure_sql(sql,self.sql_policy)+' FORMAT JSON'; data=json.dumps(parameters).encode()
        def call():
            request=urllib.request.Request(self.url.rstrip('/')+'/?database='+self.database+'&query='+urllib.parse.quote(safe),data=data,method='POST')
            request.add_header('Authorization','Basic '+base64.b64encode(f'{self.username}:{self.password}'.encode()).decode())
            with urllib.request.urlopen(request,timeout=self.policy.timeout) as response: return json.loads(response.read()).get('data',[])
        return await self.runner.run(call)
    async def cancel(self, request_id: str): return False


@dataclass
class MySQLProvider:
    host: str; port: int; username: str; password: str; database: str; sql_policy: SQLPolicy; policy: RetryPolicy = field(default_factory=RetryPolicy)
    async def health_check(self):
        result=await asyncio.to_thread(network_diagnostics,self.host,self.port,False,min(self.policy.timeout,5)); result.update({"status":"READY","provider":"MYSQL"}); return result
    async def execute(self, sql: str, parameters: dict) -> list[dict[str,Any]]:
        import pymysql
        safe=secure_sql(sql,self.sql_policy)
        def call():
            connection=pymysql.connect(host=self.host,port=self.port,user=self.username,password=self.password,database=self.database,connect_timeout=int(self.policy.timeout),read_timeout=int(self.policy.timeout),cursorclass=pymysql.cursors.DictCursor,ssl={})
            try:
                with connection.cursor() as cursor: cursor.execute(safe,parameters); return list(cursor.fetchall())
            finally: connection.close()
        return await asyncio.wait_for(asyncio.to_thread(call),self.policy.timeout)
    async def cancel(self, request_id: str): return False
