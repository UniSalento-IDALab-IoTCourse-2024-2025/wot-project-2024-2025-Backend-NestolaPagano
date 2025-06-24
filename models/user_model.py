from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class UserInDB(BaseModel):
    """
    Rappresenta il documento utente come salvato in MongoDB.
    La password sarà già hashata.
    """
    _id: Optional[str]                # Stringa ObjectId in testo
    email: EmailStr
    hashed_password: str             # Password salvata in DB (hashata)
    full_name: str
    registration_date: datetime
    connected_devices: List[str] = []


class UserPublic(BaseModel):
    """
    Rappresenta i campi che il client può effettivamente vedere.
    Non include hashed_password, né altri campi sensibili.
    """
    id: str
    email: EmailStr
    full_name: str
    registration_date: datetime
    connected_devices: List[str]


class UserRegister(BaseModel):
    """
    Schema usato per la registrazione: client invia email, password, fullName.
    """
    email: EmailStr
    password: str
    full_name: str


class UserLogin(BaseModel):
    """
    Schema usato per il login: client invia email e password in chiaro.
    """
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Schema di risposta a register e login: user pubblico + due token.
    """
    user: UserPublic
    access_token: str
    refresh_token: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None  # Può non essere sempre rigenerato

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
