export class PocApiAdapter {
    mode = 'POC';
    async json(path, init) { const r = await fetch('/api/v1' + path, { headers: { 'Content-Type': 'application/json' }, ...init }); if (!r.ok)
        throw new Error((await r.text()) || r.statusText); return r.json(); }
    createSession(role_id, options = {}) { return this.json('/sessions', { method: 'POST', body: JSON.stringify({ role_id, ...options }) }); }
    async query(session_id, question, scenario_id, parent_request_id) { const x = await this.json('/queries', { method: 'POST', body: JSON.stringify({ session_id, question, scenario_id, parent_request_id }) }); return x.request_id; }
    async events(id, onEvent) { let last = Number(sessionStorage.getItem('askdata-event-' + id) || 0), attempts = 0, done = false; while (!done && attempts < 5) {
        await new Promise((resolve, reject) => { const es = new EventSource(`/api/v1/queries/${id}/events?last_event_id=${last}`); const names = ['request.created', 'layer.started', 'layer.completed', 'answer.delta', 'request.completed', 'request.cancelled']; names.forEach(n => es.addEventListener(n, (x) => { const m = x; last = Number(m.lastEventId || last); sessionStorage.setItem('askdata-event-' + id, String(last)); onEvent({ type: n, ...JSON.parse(m.data), event_id: last }); if (n === 'request.completed' || n === 'request.cancelled') {
            done = true;
            sessionStorage.removeItem('askdata-event-' + id);
            es.close();
            resolve();
        } })); es.onerror = async () => { es.close(); if (done) {
            resolve();
            return;
        } try {
            const detail = await this.detail(id);
            if (!['PENDING', 'RUNNING'].includes(String(detail.request.status))) {
                done = true;
                sessionStorage.removeItem('askdata-event-' + id);
                onEvent({ type: 'request.completed', status: detail.request.status, recovered: true });
                resolve();
                return;
            }
        }
        catch { } reject(new Error('SSE_RECONNECT')); }; }).catch(() => { });
        if (!done) {
            attempts++;
            await new Promise(r => setTimeout(r, Math.min(1000, 150 * attempts)));
        }
    } if (!done)
        throw new Error('SSE连接重试失败，可刷新页面从Event ID恢复'); }
    detail(id) { return this.json(`/queries/${id}`); }
    cancel(id) { return this.json(`/queries/${id}/cancel`, { method: 'POST' }); }
    readiness() { return this.json('/admin/readiness'); }
    admin(path, init) { return this.json('/admin' + path, init); }
}
