FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/
COPY src /app/src
COPY scripts /app/scripts
COPY params.yaml dvc.yaml /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Model artifact is intentionally not baked into the image.
# Mount it at runtime (e.g., -v ./models:/app/models) or fetch from artifact storage.
VOLUME ["/app/models"]

EXPOSE 8000
CMD ["uvicorn", "prompt_firewall.api:app", "--host", "0.0.0.0", "--port", "8000"]
