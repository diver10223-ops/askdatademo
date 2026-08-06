import type {Adapter,RoleId,Session,QueryDetail} from '../types';
export class PocApiAdapter implements Adapter {mode='POC' as const;
 async json(path:string,init?:RequestInit){const r=await fetch('/api/v1'+path,{headers:{'Content-Type':'application/json'},...init});if(!r.ok)throw new Error((await r.text())||r.statusText);return r.json()}
 createSession(role_id:RoleId):Promise<Session>{return this.json('/sessions',{method:'POST',body:JSON.stringify({role_id})})}
 async query(session_id:string,question:string,scenario_id:string,parent_request_id?:string){const x=await this.json('/queries',{method:'POST',body:JSON.stringify({session_id,question,scenario_id,parent_request_id})});return x.request_id}
 async events(id:string,onEvent:(e:Record<string,unknown>)=>void){await new Promise<void>((resolve,reject)=>{const es=new EventSource(`/api/v1/queries/${id}/events`);let done=false;['request.created','layer.started','layer.completed','request.completed','request.cancelled'].forEach(n=>es.addEventListener(n,(x)=>{const e=JSON.parse((x as MessageEvent).data);onEvent({type:n,...e});if(n==='request.completed'||n==='request.cancelled'){done=true;es.close();resolve()}}));es.onerror=()=>{es.close();if(!done)reject(new Error('SSE连接中断'))}})}
 detail(id:string):Promise<QueryDetail>{return this.json(`/queries/${id}`)} cancel(id:string):Promise<void>{return this.json(`/queries/${id}/cancel`,{method:'POST'})} readiness(){return this.json('/admin/readiness')}
}
