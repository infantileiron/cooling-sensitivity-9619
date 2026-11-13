"""Calibration workflow: parse observations, fit a new surrogate version,
persist the audit trail, and open a sensitivity study on the calibrated model.

The source ResponseModel is never mutated; successful calibration creates a
new ResponseModel row with the refit coefficients. Rejected batches are kept
with their reason and produce no model, so the decision history is traceable.
"""
from uuid import uuid4
from sqlalchemy import select
from fastapi import HTTPException
from ..models.response_model import ResponseModel
from ..models.model_factor import ModelFactor
from ..models.model_interaction import ModelInteraction
from ..models.space import FactorSpace
from ..models.factor_range import FactorRange
from ..models.study import SensitivityStudy
from ..models.calibration import Calibration
from ..models.calibration_observation import CalibrationObservation
from ..models.common import serialize
from .model_service import specification
from .space_service import ranges
from . import calibration as engine

def expanded(db,row):
 observations=db.scalars(select(CalibrationObservation)
  .where(CalibrationObservation.calibration_id==row.id)
  .order_by(CalibrationObservation.id)).all()
 return {**serialize(row),'observations':[serialize(o) for o in observations]}

def list_all(db):
 # list view carries the parent diagnostics JSON but not the raw child
 # observations; those are returned per record by detail() for audit.
 rows=db.scalars(select(Calibration).order_by(Calibration.created_at.desc()).limit(200)).all()
 return [serialize(row) for row in rows]

def detail(db,ident):
 row=db.get(Calibration,ident)
 if row is None:raise HTTPException(404,'校准记录不存在')
 return expanded(db,row)

def _unique_model_name(db,base):
 candidate=base
 if not db.scalar(select(ResponseModel).where(ResponseModel.name==candidate)):return candidate
 suffix=uuid4().hex[:8];candidate=f'{base} · {suffix}'
 return candidate

def create(db,body):
 model_row=db.get(ResponseModel,body.model_id)
 if model_row is None:raise HTTPException(422,'代理模型不存在')
 if db.scalar(select(Calibration).where(Calibration.name==body.name)):raise HTTPException(409,'校准名称已存在')
 model=specification(db,model_row);ids=[f['factor_id'] for f in model['factors']]
 try:rows=engine.parse_observations(body.observations_csv,ids)
 except ValueError as error:raise HTTPException(422,str(error))
 try:result=engine.calibrate(model,rows)
 except ValueError as error:raise HTTPException(422,str(error))
 calibration_row=Calibration(id=str(uuid4()),name=body.name,description=body.description,
  model_id=model_row.id,status=result['status'],reject_reason=result.get('reject_reason',''),
  reject_detail=result.get('reject_detail',''),diagnostics=_diagnostics(result),
  input_sha256=result['input_sha256'])
 if result['status']=='completed':
  fitted=result['fitted_model']
  new_name=_unique_model_name(db,f'{body.name} · 校准新版代理')
  new_model=ResponseModel(id=str(uuid4()),name=new_name,
   description=f'由校准「{body.name}」基于实测冷却观测加权最小二乘重新拟合；源模型「{model_row.name}」未被修改。{body.description}',
   intercept=fitted['intercept'],response_unit='kWh')
  db.add(new_model);db.flush();calibration_row.calibrated_model_id=new_model.id
  for factor in fitted['factors']:
   db.add(ModelFactor(id=str(uuid4()),model_id=new_model.id,**{k:factor[k] for k in ['factor_id','name','unit','linear','quadratic']}))
  for pair in fitted['interactions']:
   db.add(ModelInteraction(id=str(uuid4()),model_id=new_model.id,**{k:pair[k] for k in ['left','right','coefficient']}))
  db.flush()
 db.add(calibration_row);db.flush()
 # rejected batches have no fitted values; persist the raw rows with nulls so
 # the rejected decision still has a complete observation audit trail
 for raw in result.get('observations',[{'condition_id':r['condition_id'],'point':r['point'],
    'response':r['response'],'weight':r['weight'],'fitted_value':None,'residual':None,'weighted_squared_residual':None} for r in rows]):
  db.add(CalibrationObservation(id=str(uuid4()),calibration_id=calibration_row.id,
   condition_id=raw['condition_id'],point=list(raw['point']),response=raw['response'],weight=raw['weight'],
   fitted_value=raw.get('fitted_value'),residual=raw.get('residual'),weighted_squared_residual=raw.get('weighted_squared_residual')))
 db.commit()
 return calibration_row

def _diagnostics(result):
 keys=['observation_count','condition_count','param_count','effective_rank','rank_threshold','singular_values',
  'column_scales','column_names','coefficients','coefficient_standard_errors','fitted_model',
  'raw_wssr','merged_wssr','within_wssr','reconciliation_gap','weighted_total_ss','weighted_r_squared',
  'residual_degrees_of_freedom','residual_standard_error','conditions','loco','note',
  'reject_reason','reject_detail']
 return {key:result[key] for key in keys if key in result}

def create_study(db,ident,body):
 row=db.get(Calibration,ident)
 if row is None:raise HTTPException(404,'校准记录不存在')
 if row.status!='completed' or not row.calibrated_model_id:raise HTTPException(409,'仅成功校准可建立研究')
 new_model=db.get(ResponseModel,row.calibrated_model_id)
 if new_model is None:raise HTTPException(409,'校准新版代理不存在')
 source_space=db.get(FactorSpace,body.source_space_id)
 if source_space is None or source_space.model_id!=row.model_id:
  raise HTTPException(422,'源因子空间不存在或不属于该源模型')
 if body.levels%2:raise HTTPException(422,'Morris网格级数p必须为偶数')
 if db.scalar(select(SensitivityStudy).where(SensitivityStudy.name==body.study_name)):
  raise HTTPException(409,'研究名称已存在')
 if db.scalar(select(FactorSpace).where(FactorSpace.name==body.space_name)):
  raise HTTPException(409,'因子空间名称已存在')
 source_ranges=ranges(db,source_space)
 space=FactorSpace(id=str(uuid4()),name=body.space_name,model_id=new_model.id,
  description=f'复制自源空间「{source_space.name}」，供校准新版代理「{new_model.name}」使用。{body.description}')
 db.add(space);db.flush()
 for entry in source_ranges:
  db.add(FactorRange(id=str(uuid4()),space_id=space.id,**entry))
 study=SensitivityStudy(id=str(uuid4()),name=body.study_name,model_id=new_model.id,space_id=space.id,
  trajectories=body.trajectories,levels=body.levels,power=body.power,seed=body.seed)
 db.add(study);db.flush();db.commit()
 return study
