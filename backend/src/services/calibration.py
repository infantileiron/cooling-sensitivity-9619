"""Weighted least-squares calibration of the controlled polynomial surrogate.

Measured cooling observations are merged by operating condition (replicated
points at the same factor setting), then the intercept, every factor's
linear and quadratic term and the model's already-declared interaction terms
are refit. Diagonal column scaling together with an SVD solve keeps the fit
numerically stable when factor spans differ by orders of magnitude.

Batch rejection (no surrogate is produced):
  * non-finite or non-positive measurement weights;
  * non-finite factor points or responses;
  * rank-deficient weighted design (including fewer conditions than terms);
  * fitted coefficients outside the controlled model limits;
  * non-finite fitted values.

Leave-one-condition-out (LOCO) refits drop every replicate of the held-out
condition, so repeated measurements cannot leak into the prediction error.
The raw-observation weighted residual sum of squares reconciles exactly with
the merged-condition WSSR plus the within-condition weighted dispersion:
  raw_wssr == merged_wssr + within_wssr  (up to floating point).
Coefficients stay data; no expression is ever evaluated.
"""
import csv,hashlib,io,json,math
import numpy as np
from .polynomial import validate_model

RANK_FLOOR=1e-12
OBSERVATION_LIMIT=1000

def parse_observations(text,factor_ids):
 columns=['condition_id',*factor_ids,'response','weight']
 reader=csv.DictReader(io.StringIO(text.strip()))
 if reader.fieldnames!=columns:raise ValueError('观测CSV列须为'+','.join(columns))
 rows=[]
 for line,raw in enumerate(reader,start=2):
  if any(raw.get(column) is None for column in columns):raise ValueError(f'第{line}行列不完整')
  cid=str(raw['condition_id']).strip()
  if not cid:raise ValueError(f'第{line}行工况ID为空')
  try:point=[float(raw[fid]) for fid in factor_ids]
  except (ValueError,TypeError):raise ValueError(f'第{line}行因子取值必须为数值')
  try:response=float(raw['response']);weight=float(raw['weight'])
  except (ValueError,TypeError):raise ValueError(f'第{line}行响应与权重必须为数值')
  rows.append({'condition_id':cid,'point':point,'response':response,'weight':weight})
 if not rows:raise ValueError('观测CSV至少需要一行观测')
 if len(rows)>OBSERVATION_LIMIT:raise ValueError(f'观测CSV不能超过{OBSERVATION_LIMIT}行')
 return rows

def merge_conditions(rows,factor_ids):
 groups={};order=[]
 for row in rows:
  cid=row['condition_id'];group=groups.get(cid)
  if group is None:
   group={'condition_id':cid,'point':list(row['point']),'replicates':[]}
   groups[cid]=group;order.append(cid)
  elif group['point']!=row['point']:
   raise ValueError(f'工况{cid}的重复观测因子点不一致，不能按工况合并')
  group['replicates'].append(row)
 merged=[]
 for cid in order:
  reps=groups[cid]['replicates'];total_weight=sum(r['weight'] for r in reps)
  weighted_mean=sum(r['weight']*r['response'] for r in reps)/total_weight
  within=sum(r['weight']*(r['response']-weighted_mean)**2 for r in reps)
  merged.append({'condition_id':cid,'point':list(groups[cid]['point']),'replicate_count':len(reps),
   'weight':total_weight,'response':weighted_mean,'within_wssr':within})
 return merged

def column_names(model):
 names=['intercept']
 names+=['linear:'+f['factor_id'] for f in model['factors']]
 names+=['quadratic:'+f['factor_id'] for f in model['factors']]
 names+=['interaction:'+p['left']+'*'+p['right'] for p in model['interactions']]
 return names

def design_row(model,point):
 value={f['factor_id']:point[i] for i,f in enumerate(model['factors'])}
 row=[1.0]
 row+=[value[f['factor_id']] for f in model['factors']]
 row+=[value[f['factor_id']]**2 for f in model['factors']]
 for pair in model['interactions']:row.append(value[pair['left']]*value[pair['right']])
 return row

def weighted_fit(design,weights,responses):
 """SVD weighted least squares with diagonal column scaling.

 Returns a dict with 'beta' on a full-rank weighted design, otherwise a dict
 without 'beta' carrying the numerical rank, singular values and threshold so
 the caller can reject the whole batch.
 """
 A=np.asarray(design,dtype=np.float64);w=np.asarray(weights,dtype=np.float64);y=np.asarray(responses,dtype=np.float64)
 if not (np.isfinite(A).all() and np.isfinite(w).all() and np.isfinite(y).all()):return None
 scale_sq=(w@A**2)/w.sum()
 scale=np.sqrt(np.where(scale_sq<RANK_FLOOR,1.0,scale_sq));scale[0]=1.0
 scaled=(A/scale)*np.sqrt(w)[:,None]
 if scaled.size==0 or not np.isfinite(scaled).all():return None
 _,singular,_=np.linalg.svd(scaled,full_matrices=False)
 top=singular[0] if singular.size else 0.0
 threshold=max(scaled.shape)*np.finfo(np.float64).eps*top
 rank=int(np.count_nonzero(singular>threshold))
 if top==0.0 or rank<A.shape[1]:return {'rank':rank,'threshold':float(threshold),'singular':singular.tolist(),'scale':scale.tolist()}
 u,s,vt=np.linalg.svd(scaled,full_matrices=False)
 theta=vt.T@((u.T@(np.sqrt(w)*y))/s);beta=theta/scale
 return {'beta':beta,'scale':scale,'singular':s.tolist(),'rank':rank,'threshold':float(threshold)}

def _reject(reason,detail,model,rows,merged=None):
 return {'status':'rejected','reject_reason':reason,'reject_detail':detail,
  'observation_count':len(rows),'condition_count':len(merged) if merged else None,
  'param_count':1+2*len(model['factors'])+len(model['interactions']),
  'input_sha256':_fingerprint(model,rows)}

def _fingerprint(model,rows):
 payload=json.dumps({'model':model,'observations':rows},ensure_ascii=False,sort_keys=True,separators=(',',':'))
 return hashlib.sha256(payload.encode()).hexdigest()

def calibrate(model,rows):
 model=validate_model(model);ids=[f['factor_id'] for f in model['factors']]
 param_count=1+2*len(ids)+len(model['interactions'])
 if any((not math.isfinite(r['weight'])) or r['weight']<=0.0 for r in rows):
  return _reject('non_positive_weight','存在非有限或非正权重，整批观测拒绝（加权最小二乘要求权重>0）',model,rows)
 if any(not math.isfinite(r['response']) or not all(math.isfinite(v) for v in r['point']) for r in rows):
  return _reject('non_finite_observation','存在非有限的因子取值或响应，整批观测拒绝',model,rows)
 merged=merge_conditions(rows,ids)
 design=np.array([design_row(model,group['point']) for group in merged],dtype=np.float64)
 if not np.isfinite(design).all():
  return _reject('non_finite_design','设计矩阵出现非有限值（可能溢出），整批观测拒绝',model,rows,merged)
 weights=np.array([group['weight'] for group in merged],dtype=np.float64)
 responses=np.array([group['response'] for group in merged],dtype=np.float64)
 fit=weighted_fit(design,weights,responses)
 if fit is None or 'beta' not in fit:
  detail=f"加权设计矩阵秩不足：有效秩{fit['rank'] if fit else 0}，参数数{param_count}，整批拒绝"
  return _reject('rank_deficient',detail,model,rows,merged)
 beta=fit['beta']
 if not np.isfinite(beta).all():
  return _reject('non_finite_fit','拟合系数非有限，整批观测拒绝',model,rows,merged)
 intercept=float(beta[0]);linear=beta[1:1+len(ids)];quadratic=beta[1+len(ids):1+2*len(ids)]
 pair_values=beta[1+2*len(ids):]
 pair_max=float(np.abs(pair_values).max()) if pair_values.size else 0.0
 if abs(intercept)>1e12 or max(float(np.abs(linear).max()),float(np.abs(quadratic).max()),pair_max)>1e6:
  return _reject('coefficient_limits_exceeded','拟合系数超出受控模型限值（系数≤1e6，截距≤1e12），整批拒绝',model,rows,merged)
 fitted_model={'intercept':intercept,'response_unit':'kWh',
  'factors':[{**f,'linear':float(linear[i]),'quadratic':float(quadratic[i])} for i,f in enumerate(model['factors'])],
  'interactions':[{**p,'coefficient':float(pair_values[i])} for i,p in enumerate(model['interactions'])]}
 validate_model(fitted_model)
 fitted=design@beta
 if not np.isfinite(fitted).all():
  return _reject('non_finite_fit','拟合响应非有限，整批观测拒绝',model,rows,merged)
 residuals=responses-fitted
 merged_wssr=float(weights@residuals**2)
 within_wssr=float(sum(group['within_wssr'] for group in merged))
 condition_lookup={group['condition_id']:i for i,group in enumerate(merged)}
 raw_rows=[];raw_wssr=0.0
 for row in rows:
  i=condition_lookup[row['condition_id']];hat=float(fitted[i]);residual=row['response']-hat;contribution=row['weight']*residual**2
  raw_wssr+=contribution
  raw_rows.append({'condition_id':row['condition_id'],'point':list(row['point']),'response':row['response'],
   'weight':row['weight'],'fitted_value':hat,'residual':residual,'weighted_squared_residual':contribution})
 condition_rows=[]
 for i,group in enumerate(merged):
  condition_rows.append({'condition_id':group['condition_id'],'point':list(group['point']),'replicate_count':group['replicate_count'],
   'weight':float(weights[i]),'response':float(responses[i]),'fitted_value':float(fitted[i]),
   'residual':float(residuals[i]),'weighted_squared_residual':float(weights[i]*residuals[i]**2),
   'within_wssr':float(group['within_wssr'])})
 weighted_mean=float((weights@responses)/weights.sum())
 total_ss=float(weights@(responses-weighted_mean)**2)
 r_squared=None if total_ss<=0 else float(1.0-merged_wssr/total_ss)
 n_conditions=len(merged);degrees_of_freedom=n_conditions-param_count
 sigma2=merged_wssr/degrees_of_freedom if degrees_of_freedom>0 else None
 covariance=_covariance(design,weights,fit['scale'],sigma2)
 standard_errors=None if covariance is None else [float(math.sqrt(v)) for v in np.diag(covariance)]
 loco=_loco(model,merged,design,weights,responses,total_ss)
 result={'status':'completed','reject_reason':'','reject_detail':'',
  'observation_count':len(rows),'condition_count':n_conditions,'param_count':param_count,
  'effective_rank':fit['rank'],'rank_threshold':fit['threshold'],'singular_values':fit['singular'],
  'column_scales':[float(v) for v in fit['scale']],'column_names':column_names(model),'coefficients':[float(v) for v in beta],
  'coefficient_standard_errors':standard_errors,'fitted_model':fitted_model,
  'raw_wssr':raw_wssr,'merged_wssr':merged_wssr,'within_wssr':within_wssr,
  'reconciliation_gap':raw_wssr-(merged_wssr+within_wssr),
  'weighted_total_ss':total_ss,'weighted_r_squared':r_squared,
  'residual_degrees_of_freedom':degrees_of_freedom,
  'residual_standard_error':None if sigma2 is None else float(math.sqrt(sigma2)),
  'conditions':condition_rows,'observations':raw_rows,'loco':loco,
  'input_sha256':_fingerprint(model,rows),
  'note':'按工况加权合并后做SVD加权最小二乘；列对角缩放仅用于数值稳定，报告系数为物理坐标原值。LOCO整列剔除工况（含全部重复测量）。raw_wssr=merged_wssr+within_wssr。'}
 return result

def _covariance(design,weights,scale,sigma2):
 if sigma2 is None:return None
 scaled=(design/scale)*np.sqrt(weights)[:,None]
 _,s,vt=np.linalg.svd(scaled,full_matrices=False)
 inverse_z=vt.T@np.diag(1.0/s**2)@vt
 inverse_scale=np.diag(1.0/scale)
 return (inverse_scale@inverse_z@inverse_scale)*sigma2

def _loco(model,merged,design,weights,responses,total_ss):
 rows=[];press=0.0;press_weight=0.0;complete=True
 for held in range(len(merged)):
  keep=[i for i in range(len(merged)) if i!=held]
  fit=weighted_fit(design[keep],weights[keep],responses[keep])
  point_row=np.array(design_row(model,merged[held]['point']),dtype=np.float64)
  entry={'condition_id':merged[held]['condition_id'],'held_out_response':float(responses[held]),
   'weight':float(weights[held]),'replicate_count':merged[held]['replicate_count']}
  if fit is None or 'beta' not in fit:
   complete=False;entry.update({'prediction':None,'prediction_error':None,'weighted_squared_error':None,
    'note':'剔除该工况后设计秩不足，无法给出留一预测'})
  else:
   prediction=float(point_row@fit['beta']);error=float(responses[held]-prediction)
   contribution=float(weights[held]*error**2);press+=contribution;press_weight+=weights[held]
   entry.update({'prediction':prediction,'prediction_error':error,'weighted_squared_error':contribution,'note':''})
  rows.append(entry)
 rmse=math.sqrt(press/press_weight) if complete and press_weight>0 else None
 q_squared=None if (not complete or total_ss<=0) else float(1.0-press/total_ss)
 return {'predictions':rows,'press':press if complete else None,'loco_rmse':rmse,
  'q_squared':q_squared,'complete':complete,
  'note':'每次拟合剔除整个工况及其全部重复测量，预测误差不含该工况任何信息。'}
