import os
from collections import deque
from pathlib import Path

import joblib
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

# -----------------------------
# Configuration
# -----------------------------

MODEL_PATH = Path(os.getenv("MODEL_PATH", "models/best_model.joblib"))
DRIFT_WINDOW_SIZE = int(os.getenv("DRIFT_WINDOW_SIZE", "200"))
REFERENCE_BLOCK_RATE = float(os.getenv("REFERENCE_BLOCK_RATE", "0.5"))

app = FastAPI(title="Prompt Firewall API")

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

prediction_window = deque(maxlen=DRIFT_WINDOW_SIZE)

model = None

# -----------------------------
# Prometheus Metrics
# -----------------------------

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

# -----------------------------
# Request Schema
# -----------------------------


class PromptRequest(BaseModel):
    prompt: str


# -----------------------------
# Drift Metrics Update
# -----------------------------


def _update_drift_metrics(prediction: int) -> None:
    prediction_window.append(prediction)

    blocked_rate = sum(prediction_window) / len(prediction_window)

    PREDICTION_BLOCK_RATE.set(blocked_rate)
    PREDICTION_DRIFT_ABS.set(abs(blocked_rate - REFERENCE_BLOCK_RATE))


# -----------------------------
# Startup: Load model once
# -----------------------------


@app.on_event("startup")
def load_model():
    global model

    if not MODEL_PATH.exists():
        raise RuntimeError(f"Model not found at {MODEL_PATH}")

    model = joblib.load(MODEL_PATH)


# -----------------------------
# Health Endpoint
# -----------------------------


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_path": str(MODEL_PATH),
        "model_exists": MODEL_PATH.exists(),
        "window_size": len(prediction_window),
    }


# -----------------------------
# Prediction Endpoint
# -----------------------------


@app.post("/check")
def check_prompt(payload: PromptRequest) -> dict:

    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    prediction = int(model.predict([payload.prompt])[0])

    decision = "blocked" if prediction == 1 else "allowed"

    # Prometheus counter
    PREDICTIONS_TOTAL.labels(label=str(prediction), decision=decision).inc()

    # Drift monitoring
    _update_drift_metrics(prediction)

    blocked_rate = (
        sum(prediction_window) / len(prediction_window) if len(prediction_window) > 0 else 0
    )

    return {
        "prompt": payload.prompt,
        "label": prediction,
        "decision": decision,
        "blocked_rate": blocked_rate,
        "reference_block_rate": REFERENCE_BLOCK_RATE,
        "window_size": len(prediction_window),
    }
