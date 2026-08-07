import os,tempfile
os.environ['ASKDATA_DATA_DIR']=tempfile.mkdtemp()
from fastapi.testclient import TestClient
from app.main import app
from app.db import restore_baseline

def setup_module():
    restore_baseline()

def test_admin_resource_crud_and_audit():
    with TestClient(app) as client:
        body={'id':'metric-demo','payload':{'__page':'metrics','指标名称':'演示指标','状态':'启用'},'enabled':True}
        response=client.put('/api/v1/admin/resources/assets/metric-demo',json=body)
        assert response.status_code==200
        items=client.get('/api/v1/admin/resources/assets').json()['items']
        assert any(x['id']=='metric-demo' and x['payload']['指标名称']=='演示指标' for x in items)
        body['payload']['状态']='停用'
        assert client.put('/api/v1/admin/resources/assets/metric-demo',json=body).status_code==200
        assert client.delete('/api/v1/admin/resources/assets/metric-demo').json()['deleted'] is True
        assert not any(x['id']=='metric-demo' for x in client.get('/api/v1/admin/resources/assets').json()['items'])
        audit=client.get('/api/v1/admin/logs?kind=audit').json()['items']
        assert any(x['action']=='DELETE_RESOURCE' for x in audit)

def test_all_management_resource_domains_and_mock_poc_data():
    with TestClient(app) as client:
        for kind in ('roles','assets','flows','scenarios','compliance','operations','providers','mock'):
            rid='check-'+kind
            body={'id':rid,'payload':{'__page':'automated-check','name':kind},'enabled':True}
            assert client.put(f'/api/v1/admin/resources/{kind}/{rid}',json=body).status_code==200
            assert client.delete(f'/api/v1/admin/resources/{kind}/{rid}').status_code==200
        rows=client.get('/api/v1/admin/mock/warehouse').json()['items']
        assert len(rows)==3 and {'stat_dt','org_name','loan_cur','retail_cur','corporate_cur'} <= rows[0].keys()

def test_frontend_declares_complete_management_modules():
    from pathlib import Path
    source=(Path(__file__).parents[2]/'frontend'/'src'/'AdminView.vue').read_text(encoding='utf-8')
    modules=['后台权限','用户权限','数据字典','流程配置','场景管理','查询日志','安全管控','系统运维','模型配置','数据源配置','演示管理']
    assert all(name in source for name in modules)
    assert all(name in source for name in ['Google Gemini','DeepSeek','阿里通义千问','智谱 GLM','模型提供商'])
    assert 'PAGE_SIZE=20' in source and '每页最多 20 条' in source
    assert '总行行长' in source and '分行行长' in source and '业务负责人' in source
    assert '输出图表' in source and '模型能力' in source
    assert source.count("children:[p(") >= 9
    for action in ('新增','查看/编辑','复制','删除','导出JSON'):
        assert action in source
    assert 'expanded.value=expanded.value.has(g.id)?new Set<string>():new Set([g.id])' in source
    assert "demoLogSeeds:Record<string,JsonObject[]>" in source
    assert "rows.value=items.length?items:(demoLogSeeds[active.value]||[])" in source


def test_role_dashboards_are_real_html_pages():
    from pathlib import Path
    root=Path(__file__).parents[2]/'frontend'/'public'/'dashboards'
    for name in ('head-office.html','branch-president.html','business-owner.html'):
        content=(root/name).read_text(encoding='utf-8')
        assert '<!doctype html>' in content.lower() and '返回智能问数' in content and '<table>' in content


def test_chat_page_follows_reference_and_streams_scenario_layer_details():
    from pathlib import Path
    source=(Path(__file__).parents[2]/'frontend'/'src'/'App.vue').read_text(encoding='utf-8')
    for token in ('chat-wrap','quick-chat-bar','input-footer','layer.completed','unified-trace-bubble','stream-transcript','answer.delta'):
        assert token in source
    assert 'setTimeout(()=>{if(t.running)t.waiting=true;scroll()},3000)' in source

def test_special_acceptance_resource_publish_affects_new_session_only():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        old=client.post('/api/v1/sessions',json={'role_id':'admin'}).json()
        body={'id':'rec-special','payload':{'__page':'recommendations','角色':'admin','推荐问句':'专项验收推荐问句'},'enabled':True}
        assert client.put('/api/v1/admin/resources/assets/rec-special',json=body).status_code==200
        published=client.post('/api/v1/admin/resources/publish').json()
        assert published['status']=='PUBLISHED'
        new=client.post('/api/v1/sessions',json={'role_id':'admin'}).json()
        assert old['config_version_id']!=new['config_version_id']==published['id']
        response=client.post('/api/v1/queries',json={'session_id':new['id'],'question':'贷款相关数据','scenario_id':'scenario-3'}).json()
        import time
        for _ in range(50):
            detail=client.get('/api/v1/queries/'+response['request_id']).json()
            if detail['request']['status'] not in ('PENDING','RUNNING'): break
            time.sleep(.02)
        assert '专项验收推荐问句' in detail['layers'][-1]['output']['recommendations']

def test_special_acceptance_mock_warehouse_row_crud():
    from fastapi.testclient import TestClient
    from app.main import app
    row={'stat_dt':'2026-04-30','org_name':'专项验收机构','loan_cur':1,'loan_last':2,'retail_cur':3,'retail_last':4,'corporate_cur':5,'corporate_last':6}
    with TestClient(app) as client:
        path='/api/v1/admin/mock/warehouse/2026-04-30/%E4%B8%93%E9%A1%B9%E9%AA%8C%E6%94%B6%E6%9C%BA%E6%9E%84'
        assert client.put(path,json=row).status_code==200
        assert any(x['org_name']=='专项验收机构' for x in client.get('/api/v1/admin/mock/warehouse').json()['items'])
        assert client.delete(path).status_code==200

def test_special_acceptance_masking_and_snapshot_limit():
    from app.engine import mask_results
    masked=mask_results([{'姓名':'张三','身份证':'110101199001011234','手机号':'13800138000','amount':12}])[0]
    assert masked['姓名']=='***' and masked['身份证'].startswith('110') and masked['身份证'].endswith('1234')
    assert masked['手机号'].endswith('8000') and masked['amount']==12

def test_special_acceptance_frontend_completion_tokens():
    from pathlib import Path
    root=Path(__file__).parents[2]
    app=(root/'frontend/src/App.vue').read_text()
    admin=(root/'frontend/src/AdminView.vue').read_text()
    api=(root/'frontend/src/admin-api.ts').read_text()
    poc=(root/'frontend/src/adapters/poc.ts').read_text()
    for token in ('terminalOutput(t).recommendations','terminalOutput(t).options','未执行SQL'): assert token in app
    for token in ('发布后台资源','导入JSON为草稿','完全重置','rollbackVersion','saveMockRow'): assert token in admin
    for token in ('importConfig','publishResources','deleteMockRow'): assert token in api
    for token in ('last_event_id','lastEventId','SSE_RECONNECT','sessionStorage'): assert token in poc

def test_model_logs_and_datasource_monitor_have_readable_list_and_detail():
    import time
    with TestClient(app) as client:
        session=client.post('/api/v1/sessions',json={'role_id':'admin'}).json()
        submitted=client.post('/api/v1/queries',json={'session_id':session['id'],'question':'2026年3月全行贷款投放金额','scenario_id':'scenario-1'}).json()
        for _ in range(100):
            query=client.get('/api/v1/queries/'+submitted['request_id']).json()
            if query['request']['status'] not in ('PENDING','RUNNING'):
                break
            time.sleep(.02)
        model_items=client.get('/api/v1/admin/logs?kind=model-logs').json()['items']
        source_items=client.get('/api/v1/admin/logs?kind=source-monitor').json()['items']
        model=next(x for x in model_items if x['request_id']==submitted['request_id'])
        source=next(x for x in source_items if x['request_id']==submitted['request_id'])
        assert {'operator_id','role_id','layer_code','model_provider','model','elapsed_ms'} <= model.keys()
        assert {'operator_id','role_id','source','row_count','elapsed_ms','actual_sql'} <= source.keys()
        assert client.get(f"/api/v1/admin/logs/model-logs/{model['id']}").json()['model_call']['request_id']==submitted['request_id']
        assert client.get(f"/api/v1/admin/logs/source-monitor/{source['id']}").json()['sql']['request_id']==submitted['request_id']
