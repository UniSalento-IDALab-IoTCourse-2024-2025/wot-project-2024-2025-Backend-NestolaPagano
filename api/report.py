from fastapi import APIRouter, Depends
from bson import ObjectId
from api.dependencies import get_current_user
from db.mongodb import get_database
from models.user_model import UserPublic

router = APIRouter(prefix="/api/report", tags=["report"])

@router.post("/update_maintenance", response_model=UserPublic)
async def update_user_maintenance_urgency(current_user: UserPublic = Depends(get_current_user)):
    db = await get_database()

    sessions = db.sessions.find({"user_id": ObjectId(current_user.id)})

    total = 0.0
    count = 0
    async for s in sessions:
        urg = s.get("maintenance_urgency")
        if urg is not None:
            total += float(urg)
            count += 1

    if count == 0:
        score = None
    else:
        score = total / count

    await db.users.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"maintenance_urgency": score}}
    )

    user_doc = await db.users.find_one({"_id": ObjectId(current_user.id)})

    return UserPublic(
        id=str(user_doc["_id"]),
        email=user_doc["email"],
        full_name=user_doc["full_name"],
        registration_date=user_doc["registration_date"],
        maintenance_urgency=score
    )