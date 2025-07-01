from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_current_user
from db.mongodb import get_database
from models.session_model import SessionResp
from models.user_model import UserPublic

router = APIRouter(
    prefix="/api/users",
    tags=["users"]
)

@router.get("/", response_model=List[UserPublic])
async def list_users(_current_user: UserPublic = Depends(get_current_user)):
    db = await get_database()

    query = {
        "email": {"$ne": "admin@admin.com"},
    }

    projection = {
        "email": 1,
        "full_name": 1,
        "registration_date": 1,
        "maintenance_urgency": 1
    }

    cursor = db.users.find(query, projection)

    users: List[UserPublic] = []
    async for u in cursor:
        users.append(
            UserPublic(
                id=str(u["_id"]),
                email=u["email"],
                full_name=u["full_name"],
                registration_date=u["registration_date"],
                maintenance_urgency=u.get("maintenance_urgency")
            )
        )

    return users

@router.get("/{user_id}/sessions", response_model=List[SessionResp])
async def list_user_sessions(
    user_id: str,
    _current_user: UserPublic = Depends(get_current_user)
):
    db = await get_database()
    try:
        uid = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id non valido"
        )

    cursor = db.sessions.find({"user_id": uid}).sort("start_time", 1)
    sessions: List[SessionResp] = []
    async for doc in cursor:
        sessions.append(SessionResp(
            id=str(doc["_id"]),
            user_id=str(doc["user_id"]),
            start_time=doc["start_time"],
            end_time=doc.get("end_time"),
            count_aggressive=doc.get("count_aggressive"),
            count_normal=doc.get("count_normal"),
            count_slow=doc.get("count_slow"),
            maintenance_urgency=doc.get("maintenance_urgency"),
        ))
    return sessions