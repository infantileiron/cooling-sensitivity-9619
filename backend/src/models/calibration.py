from sqlalchemy import String,Text,JSON,ForeignKey,Double
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class Calibration(RecordMixin,Base):
 __tablename__="calibrations"
 name:Mapped[str]=mapped_column(String(180),unique=True)
 description:Mapped[str]=mapped_column(Text,default="")
 model_id:Mapped[str]=mapped_column(ForeignKey("response_models.id"))
 calibrated_model_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
 status:Mapped[str]=mapped_column(String(20),default="completed")
 reject_reason:Mapped[str]=mapped_column(String(40),default="")
 reject_detail:Mapped[str]=mapped_column(Text,default="")
 diagnostics:Mapped[dict]=mapped_column(JSON,default=dict)
 input_sha256:Mapped[str]=mapped_column(String(64),default="")
