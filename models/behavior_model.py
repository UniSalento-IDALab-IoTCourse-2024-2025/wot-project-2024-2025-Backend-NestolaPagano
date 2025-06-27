from pydantic import BaseModel
from datetime import datetime
class BehaviorCreate(BaseModel):
    session_id: str
    timestamp: datetime
    label: str
    accelX: float
    accelY: float
    accelZ: float
    gyroX: float
    gyroY: float
    gyroZ: float