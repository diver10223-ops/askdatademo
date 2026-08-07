import baseline from '../../fixtures/official_baseline_v1.json';
import { isOffline } from './runtime';
const publishedKey = 'askdata-admin-published';
const draftKey = 'askdata-admin-draft';
const audits = 'askdata-admin-audits';
const resourceKey = (kind) => `askdata-admin-resources-${kind}`;
const clone = (x) => JSON.parse(JSON.stringify(x));
function localConfig() { try {
    return JSON.parse(localStorage.getItem(publishedKey) || 'null')?.payload || clone(baseline);
}
catch {
    return clone(baseline);
} }
function record(action, detail = {}) { const rows = JSON.parse(localStorage.getItem(audits) || '[]'); rows.unshift({ id: crypto.randomUUID(), action, actor: 'admin', detail, created_at: new Date().toISOString() }); localStorage.setItem(audits, JSON.stringify(rows.slice(0, 200))); }
async function request(path, init) { const response = await fetch('/api/v1/admin' + path, { headers: { 'Content-Type': 'application/json' }, ...init }); if (!response.ok)
    throw new Error(await response.text() || response.statusText); return response.json(); }
export const adminApi = {
    async baseline() { return isOffline ? localConfig() : request('/baseline'); },
    async readiness() { return isOffline ? { ready: true, roles: 3, scenarios: 8, providers: { mock: { ready: true }, sqlite: { ready: true } }, mode: 'OFFLINE' } : request('/readiness'); },
    async runtimeConfig() { return isOffline ? { checks: { PHASE1_DEMO: { ready: true }, PHASE2_DEMO: { ready: true }, PHASE2_POC: { ready: true } } } : request('/runtime-config'); },
    async logs(kind = 'requests', status = '') { if (isOffline) {
        const items = kind === 'audit' ? JSON.parse(localStorage.getItem(audits) || '[]') : [];
        return { items };
    } return request(`/logs?kind=${encodeURIComponent(kind)}${status ? `&status=${encodeURIComponent(status)}` : ''}`); },
    async approvals(status = 'PENDING') { return isOffline ? { items: [] } : request(`/approvals?status=${encodeURIComponent(status)}`); },
    async logDetail(kind, id) { if (isOffline)
        return (await this.logs(kind)).items.find((x) => String(x.id) === String(id)) || {}; return request(`/logs/${kind}/${id}`); },
    async versions() { if (isOffline) {
        const published = JSON.parse(localStorage.getItem(publishedKey) || 'null'), draft = JSON.parse(localStorage.getItem(draftKey) || 'null');
        return { items: [published, draft].filter(Boolean) };
    } return request('/config/versions'); },
    async saveDraft(name, payload) { if (isOffline) {
        const result = { id: `offline-${Date.now()}`, version: Date.now(), status: 'DRAFT', name, payload: clone(payload) };
        localStorage.setItem(draftKey, JSON.stringify(result));
        record('CREATE_DRAFT', { id: result.id, name });
        return result;
    } return request('/config/drafts', { method: 'POST', body: JSON.stringify({ name, payload }) }); },
    async publish(id) { if (isOffline) {
        const value = JSON.parse(localStorage.getItem(draftKey) || 'null');
        if (!value || value.id !== id)
            throw new Error('草稿不存在或已失效');
        localStorage.setItem(publishedKey, JSON.stringify({ ...value, status: 'PUBLISHED' }));
        localStorage.removeItem(draftKey);
        record('PUBLISH', { id, affects: 'new_sessions_only' });
        return { id, status: 'PUBLISHED', affects: 'new_sessions_only' };
    } return request(`/config/${id}/publish`, { method: 'POST' }); },
    async testProvider(kind) { if (isOffline)
        return { type: kind.toUpperCase(), status: ['mock', 'sqlite'].includes(kind) ? 'READY' : 'UNSUPPORTED_PHASE_1' }; return request(`/providers/${kind}/test`, { method: 'POST' }); },
    async resources(kind) { if (isOffline)
        return { items: JSON.parse(localStorage.getItem(resourceKey(kind)) || '[]') }; return request(`/resources/${kind}`); },
    async saveResource(kind, id, payload, enabled = true) { if (isOffline) {
        const items = (await this.resources(kind)).items.filter((x) => x.id !== id), item = { kind, id, payload, enabled, updated_at: new Date().toISOString() };
        items.push(item);
        localStorage.setItem(resourceKey(kind), JSON.stringify(items));
        record('SAVE_RESOURCE', { kind, id });
        return item;
    } return request(`/resources/${kind}/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify({ id, payload, enabled }) }); },
    async deleteResource(kind, id) { if (isOffline) {
        const items = (await this.resources(kind)).items.filter((x) => x.id !== id);
        localStorage.setItem(resourceKey(kind), JSON.stringify(items));
        record('DELETE_RESOURCE', { kind, id });
        return { deleted: true };
    } return request(`/resources/${kind}/${encodeURIComponent(id)}`, { method: 'DELETE' }); },
    async mockWarehouse() { return isOffline ? { items: clone(baseline.warehouse_rows || []) } : request('/mock/warehouse'); },
    async publishResources() { if (isOffline) {
        const result = await this.saveDraft('后台资源发布', localConfig());
        return this.publish(result.id);
    } return request('/resources/publish', { method: 'POST' }); },
    async rollback(id) { if (isOffline) {
        const items = (await this.versions()).items, value = items.find((x) => x?.id === id);
        if (!value)
            throw new Error('版本不存在');
        localStorage.setItem(publishedKey, JSON.stringify({ ...value, status: 'PUBLISHED' }));
        record('ROLLBACK', { id });
        return { id, status: 'PUBLISHED' };
    } return request(`/config/${id}/rollback`, { method: 'POST' }); },
    async importConfig(name, payload) { if (isOffline)
        return this.saveDraft(name, payload); return request('/config/import', { method: 'POST', body: JSON.stringify({ name, payload }) }); },
    async saveMockRow(row) { if (isOffline) {
        const cfg = localConfig(), items = cfg.warehouse_rows || [], i = items.findIndex((x) => x.stat_dt === row.stat_dt && x.org_name === row.org_name);
        i >= 0 ? items.splice(i, 1, row) : items.push(row);
        cfg.warehouse_rows = items;
        localStorage.setItem(publishedKey, JSON.stringify({ id: 'offline-current', status: 'PUBLISHED', payload: cfg }));
        record('SAVE_MOCK_ROW', { stat_dt: row.stat_dt, org_name: row.org_name });
        return { saved: true };
    } return request(`/mock/warehouse/${encodeURIComponent(row.stat_dt)}/${encodeURIComponent(row.org_name)}`, { method: 'PUT', body: JSON.stringify(row) }); },
    async deleteMockRow(row) { if (isOffline) {
        const cfg = localConfig();
        cfg.warehouse_rows = (cfg.warehouse_rows || []).filter((x) => !(x.stat_dt === row.stat_dt && x.org_name === row.org_name));
        localStorage.setItem(publishedKey, JSON.stringify({ id: 'offline-current', status: 'PUBLISHED', payload: cfg }));
        record('DELETE_MOCK_ROW', { stat_dt: row.stat_dt, org_name: row.org_name });
        return { deleted: true };
    } return request(`/mock/warehouse/${encodeURIComponent(row.stat_dt)}/${encodeURIComponent(row.org_name)}`, { method: 'DELETE' }); },
    async phase2Profiles() { return isOffline ? { items: [] } : request('/phase2/providers'); },
    async phase2Models() { return isOffline ? { items: [] } : request('/phase2/models'); },
    async createPhase2Model(payload) { if (isOffline)
        throw new Error('Offline Demo 不连接真实模型'); return request('/phase2/models', { method: 'POST', body: JSON.stringify(payload) }); },
    async enablePhase2Model(id) { return request(`/phase2/models/${id}/enable`, { method: 'POST' }); },
    async diagnosePhase2Model(id) { return request(`/phase2/models/${id}/diagnose`, { method: 'POST' }); },
    async phase2Datasources() { return isOffline ? { items: [] } : request('/phase2/datasources'); },
    async createPhase2Datasource(payload) { if (isOffline)
        throw new Error('Offline Demo 不连接真实数据源'); return request('/phase2/datasources', { method: 'POST', body: JSON.stringify(payload) }); },
    async enablePhase2Datasource(id) { return request(`/phase2/datasources/${id}/enable`, { method: 'POST' }); },
    async diagnosePhase2Datasource(id) { return request(`/phase2/datasources/${id}/diagnose`, { method: 'POST' }); },
    async composePhase2Profile(payload) { if (isOffline)
        throw new Error('Offline Demo 不创建运行组合'); return request('/phase2/providers/compose', { method: 'POST', body: JSON.stringify(payload) }); },
    async createPhase2Profile(payload) { if (isOffline)
        throw new Error('Offline Demo 不连接真实 Provider'); return request('/phase2/providers', { method: 'POST', body: JSON.stringify(payload) }); },
    async enablePhase2Profile(id) { return request(`/phase2/providers/${id}/enable`, { method: 'POST' }); },
    async diagnosePhase2Profile(id) { return request(`/phase2/providers/${id}/diagnose`, { method: 'POST' }); },
    async backup() { if (isOffline) {
        record('BACKUP');
        return { path: '浏览器本地配置已导出' };
    } return request('/backup', { method: 'POST' }); },
    async reset(scope) { if (isOffline) {
        if (scope === 'official') {
            localStorage.removeItem(publishedKey);
            localStorage.removeItem(draftKey);
        }
        else if (scope === 'mock-data') {
            const cfg = localConfig();
            cfg.warehouse_rows = clone(baseline.warehouse_rows);
            localStorage.setItem(publishedKey, JSON.stringify({ id: 'offline-current', status: 'PUBLISHED', payload: cfg }));
        }
        else if (scope === 'all') {
            localStorage.clear();
        }
        record(`RESET_${scope}`);
        return { status: 'ok', scope };
    } return request(`/reset/${scope}${scope === 'all' ? '?confirm=true' : ''}`, { method: 'POST' }); }
};
