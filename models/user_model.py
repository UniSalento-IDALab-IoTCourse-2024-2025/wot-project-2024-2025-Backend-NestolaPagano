from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserInDB(BaseModel):
    _id: Optional[str]
    email: EmailStr
    hashed_password: str
    full_name: str
    registration_date: datetime
    maintenance_urgency: Optional[float] = None


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    registration_date: datetime
    maintenance_urgency: Optional[float] = None



class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    user: UserPublic
    access_token: str
    refresh_token: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
