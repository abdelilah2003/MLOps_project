# Prompt Firewall MLOps Project

End-to-end MLOps project for classifying user prompts as:
- `0`: normal (allow)
- `1`: abnormal/suspicious (block)

## Stack and what each tool does
- **DVC**: reproducible stages (`prepare_data -> train -> monitor`) and parameter-driven reruns.
- **MLflow Tracking + Registry**: logs all benchmark runs, metrics/params/artifacts, registers best model version with metadata, and automatically promotes the selected best version.
- **Evidently AI**: data drift/data quality monitoring report.
- **FastAPI**: runtime inference API (`/check`) and health endpoint.
- **Prometheus + Grafana**: system/API monitoring and model-output drift monitoring.
- **Gitleaks + pip-audit + Trivy**: secret, dependency, and container image security scans in CI.
- **Dependency-Track**: SBOM analysis for dependency risk.
- **Jenkins**: CI/CD orchestration.

## Dataset location
Use your real dataset at: `data/raw/final_dataset.csv`.
The pipeline reads this path from `params.yaml` (`data.raw_path`) during `prepare_data`.

## DVC pipeline
`dvc.yaml` stages:
1. `prepare_data`
2. `train` (benchmarks 4 algorithms and selects best by metric)
3. `monitor`

Run:
```bash
dvc repro
```

## Model training and benchmarking
Training benchmarks multiple algorithms in one run:
- Logistic Regression
- Linear SVC
- Multinomial Naive Bayes
- Random Forest

Selection is controlled by `training.selection_metric` (default `f1`) in `params.yaml`.
The best model is:
1. saved to `models/model.joblib`
2. registered in MLflow Model Registry (`model.registry_name`)
3. tagged with metadata (`algorithm`, `selected_by`)
4. automatically promoted to **Production** (or tagged as production candidate fallback)

## MLflow UI (visualize experiments and registry)
1. Run training:
```bash
dvc repro train
```
2. Start MLflow UI:
```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000
```
3. Open:
- `http://localhost:5000`

You can inspect:
- benchmark runs for all algorithms
- metrics comparison
- Model Registry versions and Production stage

## Prometheus + Grafana monitoring
The API exposes Prometheus metrics at:
- `GET /metrics`

Drift-related metrics exported by API:
- `prompt_firewall_prediction_block_rate`
- `prompt_firewall_reference_block_rate`
- `prompt_firewall_prediction_drift_abs`

Start platform:
```bash
docker compose up -d api prometheus grafana
```

Access:
- API: `http://localhost:8000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin)

Grafana is pre-provisioned with a Prometheus datasource.

## Dependency-Track integration in CI/CD
Jenkins (deploy/full modes) does:
1. generate CycloneDX SBOM (`bom.json`)
2. upload SBOM to Dependency-Track

Required Jenkins env vars:
- `DEPENDENCY_TRACK_URL`
- `DEPENDENCY_TRACK_API_KEY`
- `DEPENDENCY_TRACK_PROJECT_UUID`

## Jenkins pipeline modes
- `PIPELINE_MODE=full`: quality + security + train + sbom + dependency-track + build + trivy + push
- `PIPELINE_MODE=train-only`: quality + security + train
- `PIPELINE_MODE=deploy-only`: quality + security + sbom + dependency-track + build + trivy + push

## Local checks
```bash
ruff check src tests scripts
black --check src tests scripts
pytest -q
pip-audit
docker run --rm -v "$PWD:/repo" -w /repo zricethezav/gitleaks:v8.21.2 detect --source . --redact
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.56.2 image --severity HIGH,CRITICAL your-dockerhub-user/prompt-firewall:latest
```