import baseline from '../../fixtures/official_baseline_v1.json';
import {isOffline} from './runtime';

export type JsonObject=Record<string,any>;
const publishedKey='askdata-admin-published';
const draftKey='askdata-admin-draft';
const audits='askdata-admin-audits';
const clone=<T>(x:T):T=>JSON.parse(JSON.stringify(x));
function localConfig(){try{return JSON.parse(localStorage.getItem(publishedKey)||'null')?.payload||clone(baseline)}catch{return clone(baseline)}}
function record(action:string,detail:JsonObject={}){const rows=JSON.parse(localStorage.getItem(audits)||'[]');rows.unshift({id:crypto.randomUUID(),action,actor:'admin',detail,created_at:new Date().toISOString()});localStorage.setItem(audits,JSON.stringify(rows.slice(0,200)))}
async function request(path:string,init?:RequestInit){const response=await fetch('/api/v1/admin'+path,{headers:{'Content-Type':'application/json'},...init});if(!response.ok)throw new Error(await response.text()||response.statusText);return response.json()}
export const adminApi={
 async baseline(){return isOffline?localConfig():request('/baseline')},
 async readiness(){return isOffline?{ready:true,roles:3,scenarios:8,providers:{mock:{ready:true},sqlite:{ready:true}},mode:'OFFLINE'}:request('/readiness')},
 async logs(kind='requests',status=''){if(isOffline){const items=kind==='audit'?JSON.parse(localStorage.getItem(audits)||'[]'):[];return {items}}return request(`/logs?kind=${encodeURIComponent(kind)}${status?`&status=${encodeURIComponent(status)}`:''}`)},
 async logDetail(kind:string,id:string|number){if(isOffline)return (await this.logs(kind)).items.find((x:JsonObject)=>String(x.id)===String(id))||{};return request(`/logs/${kind}/${id}`)},
 async versions(){if(isOffline){const published=JSON.parse(localStorage.getItem(publishedKey)||'null'),draft=JSON.parse(localStorage.getItem(draftKey)||'null');return {items:[published,draft].filter(Boolean)}}return request('/config/versions')},
 async saveDraft(name:string,payload:JsonObject){if(isOffline){const result={id:`offline-${Date.now()}`,version:Date.now(),status:'DRAFT',name,payload:clone(payload)};localStorage.setItem(draftKey,JSON.stringify(result));record('CREATE_DRAFT',{id:result.id,name});return result}return request('/config/drafts',{method:'POST',body:JSON.stringify({name,payload})})},
 async publish(id:string){if(isOffline){const value=JSON.parse(localStorage.getItem(draftKey)||'null');if(!value||value.id!==id)throw new Error('草稿不存在或已失效');localStorage.setItem(publishedKey,JSON.stringify({...value,status:'PUBLISHED'}));localStorage.removeItem(draftKey);record('PUBLISH',{id,affects:'new_sessions_only'});return {id,status:'PUBLISHED',affects:'new_sessions_only'}}return request(`/config/${id}/publish`,{method:'POST'})},
 async testProvider(kind:string){if(isOffline)return {type:kind.toUpperCase(),status:['mock','sqlite'].includes(kind)?'READY':'UNSUPPORTED_PHASE_1'};return request(`/providers/${kind}/test`,{method:'POST'})},
 async phase2Profiles(){return isOffline?{items:[]}:request('/phase2/providers')},
 async createPhase2Profile(payload:JsonObject){if(isOffline)throw new Error('Offline Demo 不连接真实 Provider');return request('/phase2/providers',{method:'POST',body:JSON.stringify(payload)})},
 async enablePhase2Profile(id:string){return request(`/phase2/providers/${id}/enable`,{method:'POST'})},
 async diagnosePhase2Profile(id:string){return request(`/phase2/providers/${id}/diagnose`,{method:'POST'})},
 async backup(){if(isOffline){record('BACKUP');return {path:'浏览器本地配置已导出'}}return request('/backup',{method:'POST'})},
 async reset(scope:string){if(isOffline){if(scope==='official'){localStorage.removeItem(publishedKey);localStorage.removeItem(draftKey);}record(`RESET_${scope}`);return {status:'ok',scope}}return request(`/reset/${scope}${scope==='all'?'?confirm=true':''}`,{method:'POST'})}
};
