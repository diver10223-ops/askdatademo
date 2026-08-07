import asyncio
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from cryptography.fernet import Fernet

from app.credentials import CredentialError, decrypt_secret, encrypt_secret
from app.providers.phase2 import ClickHouseProvider, OpenAICompatibleProvider, RetryPolicy
from app.sql_security import SQLPolicy, SQLSecurityError, secure_sql
from app.db import connect,restore_baseline
from app.config import PLATFORM_DB
from app.main import ProviderProfileIn,SessionIn,create_phase2_profile,enable_phase2_profile,phase2_profiles,create_session
from app.main import app
from fastapi.testclient import TestClient
from app.layers.l6_execution import ExecutionLayer
from app.models import PipelineContext


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        body = b'{"data":[{"id":"model"}]}' if self.path.endswith('/models') else (b'{"data":[{"name":"dws_loan_aggr_wide"}]}' if 'system.tables' in self.path else b'1\n')
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        length=int(self.headers.get('content-length','0')); self.rfile.read(length)
        if '/chat/completions' in self.path:
            body=json.dumps({"choices":[{"message":{"content":json.dumps({"answer":"provider answer"})}}]}).encode()
        else: body=json.dumps({"data":[{"org_name":"全行","stat_dt":"2026-03-31","current_value":980.5}]}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)


def server():
    instance=ThreadingHTTPServer(('127.0.0.1',0),Handler); Thread(target=instance.serve_forever,daemon=True).start(); return instance


def test_credentials_encrypted_and_key_required(monkeypatch):
    monkeypatch.delenv('ASKDATA_CREDENTIAL_KEY',raising=False)
    try: encrypt_secret({'password':'secret'}); assert False
    except CredentialError: pass
    monkeypatch.setenv('ASKDATA_CREDENTIAL_KEY',Fernet.generate_key().decode())
    token=encrypt_secret({'password':'secret'}); assert 'secret' not in token and decrypt_secret(token)=={'password':'secret'}


def test_sql_security():
    policy=SQLPolicy(frozenset({'dws_loan_aggr_wide'}),100)
    assert secure_sql('SELECT * FROM dws_loan_aggr_wide WHERE stat_dt=:date',policy).endswith('LIMIT 100')
    for sql in ('DELETE FROM dws_loan_aggr_wide','SELECT * FROM secret','SELECT 1; SELECT 2'):
        try: secure_sql(sql,policy); assert False
        except SQLSecurityError: pass


def test_openai_and_clickhouse_wire_protocols():
    http=server(); base=f'http://127.0.0.1:{http.server_port}'; retry=RetryPolicy(timeout=2,retries=0)
    try:
        model=OpenAICompatibleProvider(base,'key','model',retry)
        assert asyncio.run(model.health_check())['status']=='READY'
        assert asyncio.run(model.structured_generate('L7',{'answer':'x'}))['answer']=='provider answer'
        data=ClickHouseProvider(base,'user','pass','default',SQLPolicy(frozenset({'dws_loan_aggr_wide'})),retry)
        assert asyncio.run(data.health_check())['status']=='READY'
        assert asyncio.run(data.schema_check())['status']=='READY'
        rows=asyncio.run(data.execute('SELECT org_name, stat_dt, loan_cur AS current_value FROM dws_loan_aggr_wide WHERE org_name=:org AND stat_dt=:date',{'org':'全行','date':'2026-03-31'}))
        assert rows[0]['current_value']==980.5
    finally: http.shutdown()


def test_profile_api_is_encrypted_and_phase1_is_default(monkeypatch):
    restore_baseline(); monkeypatch.setenv('ASKDATA_CREDENTIAL_KEY',Fernet.generate_key().decode())
    created=create_phase2_profile(ProviderProfileIn(name='test',datasource_type='CLICKHOUSE',model_base_url='https://model.example/v1',model='m',model_api_key='model-secret',datasource_url='https://ch.example',datasource_username='u',datasource_password='db-secret',database='default',allowed_tables=['dws_loan_aggr_wide']))
    with connect(PLATFORM_DB) as db:
        raw=db.execute('select encrypted_credentials from phase2_provider_profiles where id=?',(created['id'],)).fetchone()[0]
        assert 'model-secret' not in raw and 'db-secret' not in raw
    listed=phase2_profiles()['items'][0]; assert 'encrypted_credentials' not in listed
    enable_phase2_profile(created['id'])
    phase1=create_session(SessionIn(role_id='admin')); assert phase1['execution_mode']=='PHASE1_DEMO' and phase1['provider_profile_id'] is None
    phase2=create_session(SessionIn(role_id='admin',execution_mode='PHASE2_POC',provider_profile_id=created['id'])); assert phase2['provider_profile_id']==created['id']


def test_phase2_http_query_and_sse(monkeypatch):
    restore_baseline(); monkeypatch.setenv('ASKDATA_CREDENTIAL_KEY',Fernet.generate_key().decode()); http=server(); base=f'http://127.0.0.1:{http.server_port}'
    try:
        with TestClient(app) as client:
            profile=client.post('/api/v1/admin/phase2/providers',json={'name':'wire','datasource_type':'CLICKHOUSE','model_base_url':base,'model':'model','model_api_key':'secret','datasource_url':base,'datasource_username':'u','datasource_password':'p','database':'default','allowed_tables':['dws_loan_aggr_wide'],'timeout':2,'retries':0}).json()
            assert client.post(f"/api/v1/admin/phase2/providers/{profile['id']}/enable").status_code==200
            session=client.post('/api/v1/sessions',json={'role_id':'admin','execution_mode':'PHASE2_POC','provider_profile_id':profile['id']}).json()
            query=client.post('/api/v1/queries',json={'session_id':session['id'],'question':'2026年3月全行贷款投放金额','scenario_id':'scenario-1'}).json()
            with client.stream('GET',f"/api/v1/queries/{query['request_id']}/events") as response: body=''.join(response.iter_text())
            assert 'event: request.completed' in body
            detail=client.get(f"/api/v1/queries/{query['request_id']}").json()
            assert detail['request']['mode']=='PHASE2_POC' and detail['request']['status']=='SUCCEEDED' and detail['result']
            assert detail['layers'][1]['provider']=='OPENAI_COMPATIBLE' and detail['layers'][5]['provider']=='ClickHouseProvider'
    finally: http.shutdown()


def test_phase2_failure_policy_is_not_silent():
    class Data:
        def __init__(self,fail_at): self.calls=0; self.fail_at=fail_at
        async def execute(self,*_):
            self.calls+=1
            if self.calls==self.fail_at: raise TimeoutError('hidden detail')
            return [{'current_value':1}]
    class Fixture:
        async def execute(self,*_): return [{'factor':'fallback'}]
    class Registry: pass
    def context(mode):
        value=PipelineContext('s','r','admin','v','q',mode=mode); value.sql_plan=[{'actual_sql':'SELECT 1','business_sql':'SELECT 1','parameters':{},'source':'REAL_DATASOURCE'},{'actual_sql':'SELECT 2','business_sql':'SELECT 2','parameters':{},'source':'REAL_DATASOURCE'}]; return value
    registry=Registry(); registry.fixture=Fixture(); registry.datasource=Data(1)
    failed=asyncio.run(ExecutionLayer(registry).execute(context('PHASE2_POC'))); assert failed.status=='FAILED' and failed.stop
    registry.datasource=Data(2); partial=asyncio.run(ExecutionLayer(registry).execute(context('PHASE2_POC'))); assert partial.status=='PARTIAL_SUCCESS' and partial.stop
    registry.datasource=Data(1); demo=context('PHASE2_DEMO'); succeeded=asyncio.run(ExecutionLayer(registry).execute(demo)); assert succeeded.status=='SUCCEEDED' and demo.sql_plan[0]['source']=='MOCK_FIXTURE' and demo.sql_plan[0]['fallback_reason']=='TimeoutError'
