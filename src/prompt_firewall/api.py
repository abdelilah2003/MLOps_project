import os
from pathlib import Path
import joblib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator


MODEL_PATH = Path(os.getenv("MODEL_PATH", "models/model.joblib"))
app = FastAPI(title="Prompt Firewall API")
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


class PromptRequest(BaseModel):
    prompt: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_path": str(MODEL_PATH), "model_exists": MODEL_PATH.exists()}


@app.post("/check")
def check_prompt(payload: PromptRequest) -> dict:
    if not MODEL_PATH.exists():
        raise HTTPException(status_code=503, detail=f"Model not found at {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    prediction = int(model.predict([payload.prompt])[0])
    decision = "blocked" if prediction == 1 else "allowed"
    return {"label": prediction, "decision": decision}
