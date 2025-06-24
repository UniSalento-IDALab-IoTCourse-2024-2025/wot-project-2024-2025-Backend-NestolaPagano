from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from api.dependencies import get_current_user
from core import security
from db.mongodb import get_database
from models.user_model import UserRegister, TokenResponse, UserPublic, UserLogin, TokenRefreshResponse, \
    TokenRefreshRequest, ChangePasswordRequest

import jwt

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    db = await get_database()

    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email gia registrata"
        )

    hashed_pw = security.hash_password(user_data.password)
    new_user_doc = {
        "email": user_data.email,
        "hashed_password": hashed_pw,
        "full_name": user_data.full_name,
        "registration_date": datetime.now(timezone.utc),
        "connected_devices": []
    }
    result = await db.users.insert_one(new_user_doc)
    new_user_id = str(result.inserted_id)

    payload = {"sub": new_user_id}
    access_token = security.create_access_token(data=payload)
    refresh_token = security.create_refresh_token(data=payload)

    user_public = UserPublic(
        id=new_user_id,
        email=user_data.email,
        full_name=user_data.full_name,
        registration_date=new_user_doc["registration_date"],
        connected_devices=[]
    )
    logger.info(f"Registration attempt: {user_data.full_name}")
    logger.info(f"Registration attempt: {user_data.email}")
    return TokenResponse(
        user=user_public,
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/login", response_model=TokenResponse)
async def login(creds: UserLogin):
    db = await get_database()
    user_doc = await db.users.find_one({"email": creds.email})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password non valide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    hashed_pw = user_doc["hashed_password"]
    if not security.verify_password(creds.password, hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password non valide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = str(user_doc["_id"])
    payload = {"sub": user_id}
    access_token = security.create_access_token(data=payload)
    refresh_token = security.create_refresh_token(data=payload)

    user_public = UserPublic(
        id=user_id,
        email=user_doc["email"],
        full_name=user_doc["full_name"],
        registration_date=user_doc["registration_date"],
        connected_devices=user_doc.get("connected_devices", []),
    )

    return TokenResponse(
        user=user_public,
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(body: TokenRefreshRequest):
    db = await get_database()
    try:
        payload = security.decode_token(body.refresh_token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token scaduto")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")

    new_payload = {"sub": user_id}
    new_access = security.create_access_token(data=new_payload)
    new_refresh = security.create_refresh_token(data=new_payload)

    return TokenRefreshResponse(
        access_token=new_access,
        refresh_token=new_refresh,
    )


@router.get("/me", response_model=UserPublic)
async def read_users_me(current_user: UserPublic = Depends(get_current_user)):
    """
    Endpoint protetto: richiede header Authorization: Bearer <access_token>.
    Se il token è valido, restituisce i dettagli dell’utente
    """
    return current_user

@router.post(
    "/change_password",
    response_model=UserPublic,
    status_code=status.HTTP_200_OK
)
async def change_password(
    req: ChangePasswordRequest,
    current_user: UserPublic = Depends(get_current_user)
):
    db = await get_database()

    user_doc = await db.users.find_one({"_id": ObjectId(current_user.id)})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    if not security.verify_password(req.old_password, user_doc["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password attuale non corretta"
        )

    new_hashed = security.hash_password(req.new_password)
    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"hashed_password": new_hashed}}
    )

    updated = await db.users.find_one({"_id": ObjectId(current_user.id)})

    return UserPublic(
        id=str(updated["_id"]),
        email=updated["email"],
        full_name=updated["full_name"],
        registration_date=updated["registration_date"],
        connected_devices=updated.get("connected_devices", []),
    )