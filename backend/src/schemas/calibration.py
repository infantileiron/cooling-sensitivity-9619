from pydantic import BaseModel,ConfigDict,Field,model_validator
class CalibrationCreate(BaseModel):
 model_config=ConfigDict(extra='forbid')
 name:str=Field(min_length=2,max_length=180)
 description:str=Field(default='',max_length=3000)
 model_id:str
 observations_csv:str=Field(min_length=10,max_length=400000)
class CalibrationStudyCreate(BaseModel):
 model_config=ConfigDict(extra='forbid')
 study_name:str=Field(min_length=2,max_length=180)
 source_space_id:str
 space_name:str=Field(min_length=2,max_length=180)
 description:str=Field(default='',max_length=3000)
 trajectories:int=Field(default=24,ge=2,le=128)
 levels:int=Field(default=6,ge=2,le=20)
 power:int=Field(default=12,ge=2,le=16)
 seed:int=Field(default=20261112,ge=0,le=4294967295)
 @model_validator(mode='after')
 def even_grid(self):
  if self.levels%2:raise ValueError('Morris网格级数p必须为偶数')
  return self
