from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SessionCreate(BaseModel):
    pass


class SessionStop(BaseModel):
    session_id: str


class SessionResp(BaseModel):
    id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    count_aggressive: Optional[int] = None
    count_normal: Optional[int] = None
    count_slow: Optional[int] = None
    maintenance_urgency: Optional[float] = None

