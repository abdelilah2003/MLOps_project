from pathlib import Path
import joblib
import mlflow
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


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
) -> dict:
    df = pd.read_csv(input_path)
    X_train, X_test, y_train, y_test = train_test_split(
        df["prompt"], df["label"], test_size=test_size, random_state=random_state, stratify=df["label"]
    )

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
