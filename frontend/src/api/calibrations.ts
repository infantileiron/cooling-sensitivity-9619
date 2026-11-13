import {request} from './client';
export const list=()=>request('/calibrations');
export const create=(body:unknown)=>request('/calibrations','POST',body);
export const createStudy=(id:string,body:unknown)=>request('/calibrations/'+id+'/study','POST',body);
