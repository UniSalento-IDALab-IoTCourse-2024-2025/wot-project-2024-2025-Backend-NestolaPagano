from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import joblib
import numpy as np
import pandas as pd
from typing import List

router = APIRouter()

MODEL_PATH = "ml_models/rf_driving_behavior_windows.joblib"
model_bundle = joblib.load(MODEL_PATH)
model = model_bundle['model']
class_mapping = model_bundle['class_mapping']
sampling_rate = model_bundle['sampling_rate']
window_duration_sec = model_bundle['window_duration_sec']
expected_window_len = sampling_rate * window_duration_sec

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    buffer: List[dict] = []
    try:
        while True:
            message = await websocket.receive_json()

            if message.get("type") != "window":
                continue

            payload = message.get("payload", [])
            if not isinstance(payload, list):
                continue

            buffer = payload

            if len(buffer) < expected_window_len:
                continue

            X = extract_features_from_window(buffer)
            prediction = model.predict([X])[0]
            label = class_mapping[prediction]

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