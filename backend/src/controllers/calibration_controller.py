from ..services import calibration_service as service
def list_all(db):return service.list_all(db)
def detail(db,ident):return service.detail(db,ident)
def create(db,body):
 row=service.create(db,body)
 return service.expanded(db,row)
def create_study(db,ident,body):
 from ..models.common import serialize
 study=service.create_study(db,ident,body)
 return serialize(study)
