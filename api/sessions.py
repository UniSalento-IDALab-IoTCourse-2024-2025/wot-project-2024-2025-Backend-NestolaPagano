from typing import List

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from datetime import datetime

from api.dependencies import get_current_user
from models.behavior_model import BehaviorCreate
from models.user_model    import UserPublic
from models.session_model import (
    SessionCreate,
    SessionStop,
    SessionResp,
)
from db.mongodb    import get_database

_maint_model = joblib.load("ml_models/rf_maintenance_regressor.joblib")

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

    # Aggiorna end_time
    updated = await db.sessions.find_one_and_update(
        {"_id": sid, "user_id": ObjectId(current_user.id)},
        {"$set": {"end_time": datetime.utcnow()}},
        return_document=True
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Sessione non trovata")

    behs = await db.behaviors.find({"session_id": sid}).to_list(length=None)

    # Conta le label
    count_agg = sum(1 for b in behs if b["label"] == "AGGRESSIVE")
    count_nor = sum(1 for b in behs if b["label"] == "NORMAL")
    count_slo = sum(1 for b in behs if b["label"] == "SLOW")

    # Aggiorna sessione con i conteggi
    await db.sessions.update_one(
        {"_id": sid},
        {"$set": {
            "count_aggressive": count_agg,
            "count_normal":     count_nor,
            "count_slow":       count_slo
        }}
    )

    # Ricarica la sessione aggiornata per la predizione
    final_doc = await db.sessions.find_one({"_id": sid})

    maintenance_score = await _predict_maintenance(db, final_doc, behs)

    # Aggiorna il campo maintenance_urgency
    await db.sessions.update_one(
        {"_id": sid},
        {"$set": {"maintenance_urgency": maintenance_score}}
    )

    return SessionResp(
        id=str(final_doc["_id"]),
        user_id=str(final_doc["user_id"]),
        start_time=final_doc["start_time"],
        end_time=final_doc["end_time"],
        count_aggressive=final_doc.get("count_aggressive", 0),
        count_normal=final_doc.get("count_normal", 0),
        count_slow=final_doc.get("count_slow", 0),
        maintenance_urgency=final_doc.get("maintenance_urgency", 0.0)
    )

@router.get("/", response_model=List[SessionResp])
async def list_sessions(current_user: UserPublic = Depends(get_current_user)):
    db = await get_database()
    docs = await db.sessions.find({"user_id": ObjectId(current_user.id)}).to_list(1000)
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
    docs = await db.behaviors.find({"session_id": sid}).sort("timestamp", 1).to_list(length=None)
    return [
      BehaviorCreate(
        session_id=session_id,
        timestamp=d["timestamp"],
        label=d["label"],
        accelX=d["AccX"],
        accelY=d["AccY"],
        accelZ=d["AccZ"],
        gyroX=d["GyroX"],
        gyroY=d["GyroY"],
        gyroZ=d["GyroZ"],
      )
      for d in docs
    ]

@router.get("/{session_id}", response_model=SessionResp)
async def get_session_detail(
    session_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    db = await get_database()
    sid = ObjectId(session_id)
    doc = await db.sessions.find_one({
        "_id": sid,
        "user_id": ObjectId(current_user.id)
    })
    if not doc:
        raise HTTPException(status_code=404, detail="Sessione non trovata")

    return SessionResp(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        start_time=doc["start_time"],
        end_time=doc.get("end_time"),
        count_aggressive=doc.get("count_aggressive"),
        count_normal=doc.get("count_normal"),
        count_slow=doc.get("count_slow"),
        maintenance_urgency=doc.get("maintenance_urgency"),
    )

async def _predict_maintenance(db, session_doc, behs):
    count_agg = session_doc.get("count_aggressive", 0)
    count_nor = session_doc.get("count_normal", 0)
    count_slo = session_doc.get("count_slow", 0)
    duration_minutes = (session_doc["end_time"] - session_doc["start_time"]).total_seconds() / 60.0

    acc_mags = [np.sqrt(b["AccX"]**2 + b["AccY"]**2 + b["AccZ"]**2) for b in behs]
    gyro_mags = [np.sqrt(b["GyroX"]**2 + b["GyroY"]**2 + b["GyroZ"]**2) for b in behs]

    accel_mag_mean = float(np.mean(acc_mags)) if acc_mags else 0.0
    accel_mag_std  = float(np.std(acc_mags))  if acc_mags else 0.0
    gyro_mag_mean  = float(np.mean(gyro_mags)) if gyro_mags else 0.0
    gyro_mag_std   = float(np.std(gyro_mags))  if gyro_mags else 0.0

    X = pd.DataFrame([{
        "count_aggressive": count_agg,
        "count_normal": count_nor,
        "count_slow": count_slo,
        "duration_minutes": duration_minutes,
        "accel_mag_mean": accel_mag_mean,
        "accel_mag_std": accel_mag_std,
        "gyro_mag_mean": gyro_mag_mean,
        "gyro_mag_std": gyro_mag_std
    }])
    pred = _maint_model.predict(X)[0]
    return float(pred)