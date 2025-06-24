from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from datetime import datetime

from api.dependencies import get_current_user
from models.user_model    import UserPublic
from models.session_model import (
    SessionCreate,
    SessionStop,
    SessionResp,
    BehaviorCreate
)
from db.mongodb    import get_database

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.post("/", response_model=SessionResp, status_code=status.HTTP_201_CREATED)
async def start_session(
    _: SessionCreate,
    current_user: UserPublic = Depends(get_current_user),
):
    db = await get_database()
    doc = {
        "user_id": ObjectId(current_user.id),
        "start_time": datetime.utcnow(),
        "end_time": None
    }
    res = await db.sessions.insert_one(doc)
    return SessionResp(
        id=str(res.inserted_id),
        user_id=current_user.id,
        start_time=doc["start_time"],
        end_time=None
    )


@router.patch("/stop", response_model=SessionResp)
async def stop_session(
    body: SessionStop,
    current_user: UserPublic = Depends(get_current_user),
):
    db = await get_database()
    sid = ObjectId(body.session_id)
    updated = await db.sessions.find_one_and_update(
        {"_id": sid, "user_id": ObjectId(current_user.id)},
        {"$set": {"end_time": datetime.utcnow()}},
        return_document=True
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Sessione non trovata")
    return SessionResp(
        id=str(updated["_id"]),
        user_id=str(updated["user_id"]),
        start_time=updated["start_time"],
        end_time=updated["end_time"]
    )


@router.post("/behaviors", status_code=status.HTTP_201_CREATED)
async def add_behavior(
    body: BehaviorCreate,
    current_user: UserPublic = Depends(get_current_user),
):
    db = await get_database()
    sid = ObjectId(body.session_id)

    session_doc = await db.sessions.find_one({
        "_id": sid,
        "user_id": ObjectId(current_user.id)
    })
    if not session_doc:
        raise HTTPException(status_code=404, detail="Sessione non trovata")
    await db.behaviors.insert_one({
        "session_id": sid,
        "timestamp":  body.timestamp,
        "label":      body.label,
    })
    return {"ok": True}

@router.get("/", response_model=List[SessionResp])
async def list_sessions(current_user: UserPublic = Depends(get_current_user)):
    db = await get_database()
    docs = await db.sessions.find({"user_id": ObjectId(current_user.id)}).to_list(100)
    return [
        SessionResp(
          id=str(d["_id"]),
          user_id=str(d["user_id"]),
          start_time=d["start_time"],
          end_time=d["end_time"] or d["start_time"],
        )
        for d in docs
    ]

@router.get("/{session_id}/behaviors", response_model=List[BehaviorCreate])
async def get_behaviors(
    session_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    db = await get_database()
    sid = ObjectId(session_id)

    ses = await db.sessions.find_one({"_id": sid, "user_id": ObjectId(current_user.id)})
    if not ses:
        raise HTTPException(status_code=404, detail="Sessione non trovata")
    docs = await db.behaviors.find({"session_id": sid}).sort("timestamp", 1).to_list(1000)
    return [
      BehaviorCreate(
        session_id=session_id,
        timestamp=d["timestamp"],
        label=d["label"],
      )
      for d in docs
    ]