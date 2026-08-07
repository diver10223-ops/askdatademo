export type RoleId='admin'|'beijing'|'retail';
export interface Session {id:string;role_id:RoleId;config_version_id:string}
export interface QueryDetail {request:Record<string,unknown>;layers:Array<Record<string,unknown>>;sql_executions:Array<Record<string,unknown>>;result:Array<Record<string,unknown>>}
export interface Adapter {mode:'POC'|'OFFLINE';createSession(role_id:RoleId,options?:Record<string,unknown>):Promise<Session>;query(session:string,question:string,scenario:string,parent?:string):Promise<string>;events(id:string,onEvent:(event:Record<string,unknown>)=>void):Promise<void>;detail(id:string):Promise<QueryDetail>;cancel(id:string):Promise<void>;readiness():Promise<Record<string,unknown>>;admin(path:string,init?:RequestInit):Promise<any>}
