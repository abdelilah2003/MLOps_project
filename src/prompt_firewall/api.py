import os
from collections import deque
from pathlib import Path

import joblib
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

MODEL_PATH = Path(os.getenv("MODEL_PATH", "models/model.joblib"))
DRIFT_WINDOW_SIZE = int(os.getenv("DRIFT_WINDOW_SIZE", "200"))
REFERENCE_BLOCK_RATE = float(os.getenv("REFERENCE_BLOCK_RATE", "0.5"))

app = FastAPI(title="Prompt Firewall API")
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

prediction_window = deque(maxlen=DRIFT_WINDOW_SIZE)

PREDICTIONS_TOTAL = Counter(
    "prompt_firewall_predictions_total",
    "Total number of predictions made by the prompt firewall",
    ["label", "decision"],
)
PREDICTION_BLOCK_RATE = Gauge(
    "prompt_firewall_prediction_block_rate",
    "Rolling blocked prediction rate over recent requests",
)
REFERENCE_BLOCK_RATE_GAUGE = Gauge(
    "prompt_firewall_reference_block_rate",
    "Expected reference blocked rate used as drift baseline",
)
PREDICTION_DRIFT_ABS = Gauge(
    "prompt_firewall_prediction_drift_abs",
    "Absolute difference between rolling blocked rate and reference blocked rate",
)

REFERENCE_BLOCK_RATE_GAUGE.set(REFERENCE_BLOCK_RATE)


class PromptRequest(BaseModel):
    prompt: str


def _update_drift_metrics(prediction: int) -> None:
    prediction_window.append(prediction)
    blocked_rate = sum(prediction_window) / len(prediction_window)
    PREDICTION_BLOCK_RATE.set(blocked_rate)
    PREDICTION_DRIFT_ABS.set(abs(blocked_rate - REFERENCE_BLOCK_RATE))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_path": str(MODEL_PATH),
        "model_exists": MODEL_PATH.exists(),
    }


@app.post("/check")
def check_prompt(payload: PromptRequest) -> dict:
    if not MODEL_PATH.exists():
        raise HTTPException(status_code=503, detail=f"Model not found at {MODEL_PATH}")

    model = joblib.load(MODEL_PATH)
    prediction = int(model.predict([payload.prompt])[0])
    decision = "blocked" if prediction == 1 else "allowed"

    PREDICTIONS_TOTAL.labels(label=str(prediction), decision=decision).inc()
    _update_drift_metrics(prediction)

    return {"label": prediction, "decision": decision}