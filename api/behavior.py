from bson import ObjectId
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import joblib
import numpy as np
import pandas as pd
from typing import List

from db.mongodb import get_database

router = APIRouter(prefix="/api/behavior", tags=["behavior"])

MODEL_PATH = "ml_models/rf_driving_behavior_windows.joblib"
model_bundle = joblib.load(MODEL_PATH)
model = model_bundle['model']
class_mapping = model_bundle['class_mapping']
sampling_rate = model_bundle['sampling_rate']
window_duration_sec = model_bundle['window_duration_sec']
expected_window_len = sampling_rate * window_duration_sec

@router.websocket("/")
async def predict_behavior(websocket: WebSocket):
    await websocket.accept()
    db = await get_database()
    try:
        while True:
            message = await websocket.receive_json()

            if message.get("type") != "window":
                continue

            payload = message.get("payload", [])
            session_id = message.get("session_id")

            if not isinstance(payload, list) or not session_id:
                continue

            if len(payload) < expected_window_len:
                continue

            # Predizione
            X = extract_features_from_window(payload)
            prediction = model.predict([X])[0]
            label = class_mapping[prediction]

            # Salvataggio dei dati
            sid = ObjectId(session_id)
            docs = []
            for p in payload:
                docs.append({
                    "session_id": sid,
                    "timestamp":  p["timestamp"],
                    "label":      label,
                    "AccX":       p["AccX"],
                    "AccY":       p["AccY"],
                    "AccZ":       p["AccZ"],
                    "GyroX":      p["GyroX"],
                    "GyroY":      p["GyroY"],
                    "GyroZ":      p["GyroZ"],
                })
            if docs:
                await db.behaviors.insert_many(docs)

            # Invia la label all'app
            await websocket.send_json({
                "type": "prediction",
                "label": label
            })

    except WebSocketDisconnect:
        print("Connessione WebSocket chiusa")

def extract_features_from_window(window: List[dict]) -> List[float]:
    df = pd.DataFrame(window)

    df["Acc_Mag"] = np.sqrt(df["AccX"]**2 + df["AccY"]**2 + df["AccZ"]**2)
    df["Gyro_Mag"] = np.sqrt(df["GyroX"]**2 + df["GyroY"]**2 + df["GyroZ"]**2)

    cols = ["AccX", "AccY", "AccZ", "GyroX", "GyroY", "GyroZ", "Acc_Mag", "Gyro_Mag"]
    features = []

    for col in cols:
        arr = df[col].values
        features.extend([
            arr.mean(),
            arr.std(),
            arr.min(),
            arr.max()
        ])
    return features