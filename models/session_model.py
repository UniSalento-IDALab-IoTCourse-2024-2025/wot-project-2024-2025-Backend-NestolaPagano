# app/models/session_model.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SessionCreate(BaseModel):
    """
    Richiesta di creazione sessione.
    Non serve campo perché l'utente è ricavato dal token.
    """
    pass


class SessionStop(BaseModel):
    """
    Richiesta di termine sessione.
    """
    session_id: str


class SessionResp(BaseModel):
    """
    Risposta a creazione/stop sessione.
    """
    id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None


class BehaviorCreate(BaseModel):
    """
    Salvataggio di una predizione intra‑sessione.
    """
    session_id: str
    timestamp: datetime
    label: str