export class PocApiAdapter {
    mode = 'POC';
    async json(path, init) { const r = await fetch('/api/v1' + path, { headers: { 'Content-Type': 'application/json' }, ...init }); if (!r.ok)
        throw new Error((await r.text()) || r.statusText); return r.json(); }
    createSession(role_id, options = {}) { return this.json('/sessions', { method: 'POST', body: JSON.stringify({ role_id, ...options }) }); }
    async query(session_id, question, scenario_id, parent_request_id) { const x = await this.json('/queries', { method: 'POST', body: JSON.stringify({ session_id, question, scenario_id, parent_request_id }) }); return x.request_id; }
    async events(id, onEvent) { await new Promise((resolve, reject) => { const es = new EventSource(`/api/v1/queries/${id}/events`); let done = false; ['request.created', 'layer.started', 'layer.completed', 'request.completed', 'request.cancelled'].forEach(n => es.addEventListener(n, (x) => { const e = JSON.parse(x.data); onEvent({ type: n, ...e }); if (n === 'request.completed' || n === 'request.cancelled') {
        done = true;
        es.close();
        resolve();
    } })); es.onerror = () => { es.close(); if (!done)
        reject(new Error('SSE连接中断')); }; }); }
    detail(id) { return this.json(`/queries/${id}`); }
    cancel(id) { return this.json(`/queries/${id}/cancel`, { method: 'POST' }); }
    readiness() { return this.json('/admin/readiness'); }
    admin(path, init) { return this.json('/admin' + path, init); }
}
