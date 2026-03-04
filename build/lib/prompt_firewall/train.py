from pathlib import Path
import joblib
import mlflow
import pandas as pd
from mlflow import MlflowClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier


def _compute_metrics(y_true, y_pred) -> dict:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }


def _candidate_models(random_state: int, max_features: int, c_value: float) -> dict:
    return {
        "logistic_regression": Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(max_features=max_features)),
                ("clf", LogisticRegression(C=c_value, random_state=random_state, max_iter=500)),
            ]
        ),
        "linear_svc": Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(max_features=max_features)),
                ("clf", LinearSVC(C=c_value, random_state=random_state)),
            ]
        ),
        "multinomial_nb": Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(max_features=max_features)),
                ("clf", MultinomialNB()),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(max_features=max_features)),
                (
                    "clf",
                    RandomForestClassifier(
                        n_estimators=200,
                        random_state=random_state,
                        class_weight="balanced",
                    ),
                ),
            ]
        ),
    }


def train_and_log(
    input_path: Path,
    model_path: Path,
    metrics_path: Path,
    tracking_uri: str,
    experiment_name: str,
    random_state: int,
    test_size: float,
    max_features: int,
    c_value: float,
    registry_model_name: str,
    selection_metric: str,
) -> dict:
    df = pd.read_csv(input_path)
    X_train, X_test, y_train, y_test = train_test_split(
        df["prompt"],
        df["label"],
        test_size=test_size,
        random_state=random_state,
        stratify=df["label"],
    )

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    candidates = _candidate_models(
        random_state=random_state,
        max_features=max_features,
        c_value=c_value,
    )

    best_name = None
    best_model = None
    best_metrics = None
    best_metric_value = -1.0

    for model_name, model in candidates.items():
        with mlflow.start_run(run_name=f"benchmark_{model_name}") as run:
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            metrics = _compute_metrics(y_test, preds)

            mlflow.log_params(
                {
                    "algorithm": model_name,
                    "random_state": random_state,
                    "test_size": test_size,
                    "max_features": max_features,
                    "c_value": c_value,
                    "selection_metric": selection_metric,
                }
            )
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(model, artifact_path="model")

            metric_value = float(metrics[selection_metric])
            if metric_value > best_metric_value:
                best_metric_value = metric_value
                best_name = model_name
                best_model = model
                best_metrics = metrics
                best_run_id = run.info.run_id

    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, model_path)

    benchmark_summary = {
        "best_algorithm": best_name,
        "selection_metric": selection_metric,
        "best_run_id": best_run_id,
        "metrics": best_metrics,
    }
    pd.DataFrame([benchmark_summary]).to_json(metrics_path, orient="records", indent=2)

    client = MlflowClient()
    model_uri = f"runs:/{best_run_id}/model"
    registered = mlflow.register_model(model_uri=model_uri, name=registry_model_name)
    client.set_model_version_tag(
        name=registry_model_name,
        version=registered.version,
        key="selected_by",
        value=selection_metric,
    )
    client.set_model_version_tag(
        name=registry_model_name,
        version=registered.version,
        key="algorithm",
        value=best_name,
    )

    try:
        client.transition_model_version_stage(
            name=registry_model_name,
            version=registered.version,
            stage="Production",
            archive_existing_versions=True,
        )
    except Exception:
        client.set_registered_model_tag(
            name=registry_model_name,
            key="production_candidate_version",
            value=str(registered.version),
        )

    return benchmark_summary
    clf = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(max_features=max_features)),
            ("lr", LogisticRegression(C=c_value, random_state=random_state, max_iter=500)),
        ]
    )
    clf.fit(X_train, y_train)
    preds = clf.predict(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, preds),
        "precision": precision_score(y_test, preds, zero_division=0),
        "recall": recall_score(y_test, preds, zero_division=0),
        "f1": f1_score(y_test, preds, zero_division=0),
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, model_path)

    pd.DataFrame([metrics]).to_json(metrics_path, orient="records", indent=2)

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run():
        mlflow.log_params(
            {
                "random_state": random_state,
                "test_size": test_size,
                "max_features": max_features,
                "c_value": c_value,
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.log_artifact(str(metrics_path))
        mlflow.sklearn.log_model(clf, artifact_path="model")

    return metrics
