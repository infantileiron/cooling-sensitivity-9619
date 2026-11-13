from sqlalchemy import String,Text,JSON,ForeignKey,Double
from sqlalchemy.orm import Mapped,mapped_column
from .common import RecordMixin
from ..config.database import Base
class CalibrationObservation(RecordMixin,Base):
 __tablename__="calibration_observations"
 calibration_id:Mapped[str]=mapped_column(ForeignKey("calibrations.id"),index=True)
 condition_id:Mapped[str]=mapped_column(String(64))
 point:Mapped[dict]=mapped_column(JSON)
 response:Mapped[float]=mapped_column(Double)
 weight:Mapped[float]=mapped_column(Double)
 fitted_value:Mapped[float|None]=mapped_column(Double,nullable=True)
 residual:Mapped[float|None]=mapped_column(Double,nullable=True)
 weighted_squared_residual:Mapped[float|None]=mapped_column(Double,nullable=True)
