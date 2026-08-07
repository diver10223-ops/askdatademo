import json, sqlite3, shutil, zipfile
from datetime import datetime, timezone
from pathlib import Path
from .config import DATA_DIR, PLATFORM_DB, WAREHOUSE_DB, BASELINE

def merge_defaults(defaults, value):
 result=dict(defaults)
 for key,item in value.items(): result[key]=merge_defaults(result.get(key,{}),item) if isinstance(item,dict) and isinstance(result.get(key),dict) else item
 return result

def connect(path:Path):
 c=sqlite3.connect(path,check_same_thread=False); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def migrate():
 DATA_DIR.mkdir(parents=True,exist_ok=True)
 with connect(PLATFORM_DB) as c:
  c.executescript('''
CREATE TABLE IF NOT EXISTS config_versions(id TEXT PRIMARY KEY,name TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('DRAFT','PUBLISHED','DISABLED','ARCHIVED')),version INTEGER NOT NULL UNIQUE,payload TEXT NOT NULL,official INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_published ON config_versions(status) WHERE status='PUBLISHED';
CREATE TABLE IF NOT EXISTS roles(id TEXT PRIMARY KEY,name TEXT NOT NULL,enabled INTEGER NOT NULL,permissions TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,role_id TEXT NOT NULL,permission_snapshot_id TEXT NOT NULL,permission_snapshot TEXT NOT NULL,config_version_id TEXT NOT NULL REFERENCES config_versions(id),context TEXT NOT NULL DEFAULT '{}',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(active,created_at);
CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(id),parent_request_id TEXT REFERENCES requests(id),trace_id TEXT NOT NULL,scenario_id TEXT,case_id TEXT,question TEXT NOT NULL,mode TEXT NOT NULL,status TEXT NOT NULL,last_layer TEXT,termination_reason TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0,cancelled_by TEXT,cancelled_at TEXT,config_version_id TEXT NOT NULL,created_at TEXT NOT NULL,completed_at TEXT);
CREATE INDEX IF NOT EXISTS idx_request_parent ON requests(parent_request_id); CREATE INDEX IF NOT EXISTS idx_request_session ON requests(session_id,created_at);
CREATE TABLE IF NOT EXISTS layer_executions(id INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT NOT NULL REFERENCES requests(id),layer_code TEXT NOT NULL,status TEXT NOT NULL,input_json TEXT NOT NULL,output_json TEXT,provider TEXT,elapsed_ms REAL,error_code TEXT,UNIQUE(request_id,layer_code));
CREATE TABLE IF NOT EXISTS sse_events(request_id TEXT NOT NULL REFERENCES requests(id),event_id INTEGER NOT NULL,event_type TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(request_id,event_id));
CREATE INDEX IF NOT EXISTS idx_event_seq ON sse_events(request_id,event_id);
CREATE TABLE IF NOT EXISTS sql_executions(id INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT NOT NULL REFERENCES requests(id),sequence INTEGER NOT NULL,business_sql TEXT NOT NULL,actual_sql TEXT NOT NULL,parameters TEXT NOT NULL,source TEXT NOT NULL,status TEXT NOT NULL,row_count INTEGER,elapsed_ms REAL,error TEXT,fallback INTEGER NOT NULL DEFAULT 0,UNIQUE(request_id,sequence));
CREATE TABLE IF NOT EXISTS result_snapshots(request_id TEXT PRIMARY KEY REFERENCES requests(id),payload TEXT NOT NULL,masked INTEGER NOT NULL,size_bytes INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT NOT NULL,actor TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approval_tasks(id TEXT PRIMARY KEY,type TEXT NOT NULL,title TEXT NOT NULL,applicant_id TEXT NOT NULL,applicant_name TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED')),submitted_at TEXT NOT NULL,target_type TEXT,target_id TEXT);
CREATE TABLE IF NOT EXISTS provider_configs(id TEXT PRIMARY KEY,type TEXT NOT NULL,status TEXT NOT NULL,config TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_resources(kind TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL,PRIMARY KEY(kind,id));
CREATE TABLE IF NOT EXISTS phase2_provider_profiles(id TEXT PRIMARY KEY,name TEXT NOT NULL,model_type TEXT NOT NULL CHECK(model_type='OPENAI_COMPATIBLE'),datasource_type TEXT NOT NULL CHECK(datasource_type IN ('CLICKHOUSE','MYSQL')),public_config TEXT NOT NULL,encrypted_credentials TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('DRAFT','ENABLED','DISABLED')),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS phase2_model_configs(id TEXT PRIMARY KEY,name TEXT NOT NULL,provider TEXT NOT NULL,public_config TEXT NOT NULL,encrypted_credentials TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('DRAFT','ENABLED','DISABLED')),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS phase2_datasource_configs(id TEXT PRIMARY KEY,name TEXT NOT NULL,type TEXT NOT NULL CHECK(type IN ('CLICKHOUSE','MYSQL')),public_config TEXT NOT NULL,encrypted_credentials TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('DRAFT','ENABLED','DISABLED')),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS phase2_session_profiles(session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,profile_id TEXT NOT NULL REFERENCES phase2_provider_profiles(id),execution_mode TEXT NOT NULL CHECK(execution_mode IN ('PHASE2_DEMO','PHASE2_POC')));
CREATE TABLE IF NOT EXISTS session_execution_modes(session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,execution_mode TEXT NOT NULL CHECK(execution_mode IN ('PHASE1_DEMO','PHASE2_DEMO','PHASE2_POC')));
CREATE TABLE IF NOT EXISTS provider_diagnostics(id INTEGER PRIMARY KEY AUTOINCREMENT,profile_id TEXT NOT NULL,component TEXT NOT NULL,status TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
''')
  defaults=json.loads((BASELINE.parent/'demo_runtime_defaults.json').read_text())
  for row in c.execute('SELECT id,payload FROM config_versions').fetchall():
   payload=json.loads(row['payload'])
   merged=merge_defaults(defaults,payload.get('runtime',{}))
   if merged!=payload.get('runtime'):
    payload['runtime']=merged
    c.execute('UPDATE config_versions SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),row['id']))
 with connect(WAREHOUSE_DB) as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS dws_loan_aggr_wide(stat_dt TEXT NOT NULL,org_name TEXT NOT NULL,loan_cur REAL,loan_last REAL,retail_cur REAL,retail_last REAL,corporate_cur REAL,corporate_last REAL,PRIMARY KEY(stat_dt,org_name)); CREATE INDEX IF NOT EXISTS idx_loan_org_date ON dws_loan_aggr_wide(org_name,stat_dt);''')

def restore_baseline(reset_mock=True):
 migrate(); b=json.loads(BASELINE.read_text()); b.setdefault('runtime',json.loads((BASELINE.parent/'demo_runtime_defaults.json').read_text())); now=datetime.now(timezone.utc).isoformat()
 with connect(PLATFORM_DB) as c:
  c.execute("INSERT OR IGNORE INTO config_versions VALUES(?,?,?,?,?,?,?)",('official-v1','Official Demo Baseline v1','PUBLISHED',1,json.dumps(b,ensure_ascii=False),1,now))
  for r in b['roles']: c.execute("INSERT OR REPLACE INTO roles VALUES(?,?,1,?)",(r['id'],r['name'],json.dumps(r,ensure_ascii=False)))
  c.execute("INSERT OR IGNORE INTO provider_configs VALUES('mock-model','MOCK','READY','{}')")
  c.execute("INSERT OR IGNORE INTO provider_configs VALUES('sqlite','SQLITE','READY','{}')")
  c.executemany("INSERT OR IGNORE INTO approval_tasks VALUES(?,?,?,?,?,'PENDING',?,?,?)",[
   ('approval-metric','指标发布','贷款投放指标口径变更申请','wang.owner','王总（业务负责人）','2026-08-07T09:35:00+00:00','METRIC','loan_cur'),
   ('approval-role','权限申请','北京分行经营数据导出权限申请','li.zong','李总（分行行长）','2026-08-07T09:12:00+00:00','PERMISSION','rights-branch'),
   ('approval-model','配置发布','Gemini模型配置启用申请','config.admin','配置管理员','2026-08-07T08:46:00+00:00','MODEL','gemini-default')])
 if reset_mock:
  with connect(WAREHOUSE_DB) as c:
   c.execute('DELETE FROM dws_loan_aggr_wide')
   c.executemany('INSERT INTO dws_loan_aggr_wide VALUES(:stat_dt,:org_name,:loan_cur,:loan_last,:retail_cur,:retail_last,:corporate_cur,:corporate_last)',b['warehouse_rows'])

def restore_official_config():
 migrate()
 with connect(PLATFORM_DB) as c:
  c.execute("UPDATE config_versions SET status='ARCHIVED' WHERE status='PUBLISHED' AND id<>'official-v1'")
  c.execute("UPDATE config_versions SET status='PUBLISHED' WHERE id='official-v1'")
  c.execute("INSERT INTO audit_logs(action,actor,detail,created_at) VALUES('RESTORE_OFFICIAL','admin','{}',?)",(datetime.now(timezone.utc).isoformat(),))

def backup(dest:Path):
 dest.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(dest,'w') as z:
  z.write(PLATFORM_DB,'platform.db'); z.write(WAREHOUSE_DB,'mock_warehouse.db')
 return dest

def restore_backup(source:Path):
 if not source.exists(): raise FileNotFoundError(source)
 with zipfile.ZipFile(source) as z:
  if set(z.namelist()) != {'platform.db','mock_warehouse.db'}: raise ValueError('invalid backup')
  extracted=[]
  for name,target in (('platform.db',PLATFORM_DB),('mock_warehouse.db',WAREHOUSE_DB)):
   temporary=target.with_suffix('.restore')
   with z.open(name) as src, temporary.open('wb') as dst: shutil.copyfileobj(src,dst)
   with connect(temporary) as db:
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('invalid database')
   extracted.append((temporary,target))
  for temporary,target in extracted: temporary.replace(target)

def full_reset():
 for p in (PLATFORM_DB,WAREHOUSE_DB):
  if p.exists(): p.unlink()
 restore_baseline()
