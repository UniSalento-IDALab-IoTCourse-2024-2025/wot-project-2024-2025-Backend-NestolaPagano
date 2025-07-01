from typing import List

from fastapi import APIRouter, Depends
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from api.dependencies import get_current_user
from db.mongodb import get_database
from models.user_model import UserPublic, UserAvgBehavior

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

@router.get(
    "/avg_behavior_by_user",
    response_model=List[UserAvgBehavior]
)
async def avg_behavior_by_user(_current_user: UserPublic = Depends(get_current_user)) -> List[UserAvgBehavior]:
    db: AsyncIOMotorDatabase = await get_database()

    # Filtra utenti diversi da admin
    users_cursor = db.users.find({
        "email": {"$ne": "admin@admin.com"},
        "full_name": {"$ne": "admin"}
    }, {
        "_id": 1,
        "full_name": 1
    })
    users = await users_cursor.to_list(length=None)
    if not users:
        return []

    # Per ogni utente, aggrega tutti i comportamenti
    results = []
    for u in users:
        uid = u["_id"]

        pipeline = [
            {"$match": {"user_id": uid}},
            {"$lookup": {
                "from": "behaviors",
                "localField": "_id",
                "foreignField": "session_id",
                "as": "bs"
            }},
            {"$unwind": "$bs"},
            {"$group": {
                "_id": None,
                "avg": {
                    "$avg": {
                        "$switch": {
                            "branches": [
                                {"case": {"$eq": ["$bs.label", "SLOW"]},     "then": 0.0},
                                {"case": {"$eq": ["$bs.label", "NORMAL"]},   "then": 1.0},
                                {"case": {"$eq": ["$bs.label", "AGGRESSIVE"]},"then": 2.0},
                            ],
                            "default": 0.0
                        }
                    }
                }
            }}
        ]

        agg = await db.sessions.aggregate(pipeline).to_list(length=1)
        avg_val = agg[0]["avg"] if agg else 0.0

        results.append(UserAvgBehavior(
            full_name = u["full_name"],
            avg_behavior = round(avg_val, 3)
        ))

    return results