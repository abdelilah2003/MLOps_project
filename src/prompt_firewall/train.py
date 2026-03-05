from pathlib import Path
import joblib
import mlflow
import pandas as pd
from mlflow import MlflowClient
import yaml


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

# ALGORITHMS
from sklearn.svm import LinearSVC  # noqa: F401
from sklearn.naive_bayes import MultinomialNB  # noqa: F401
from sklearn.ensemble import RandomForestClassifier  # noqa: F401


def _compute_metrics(y_true, y_pred) -> dict:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }


def build_model(random_state: int, max_features: int, c_value: float):
    """
    SELECT ONE MODEL ONLY
    Comment / uncomment to test different algorithms
    """

    # --- MODEL 1: Logistic Regression ---
    model = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(max_features=max_features)),
            ("clf", LogisticRegression(C=c_value, random_state=random_state, max_iter=500)),
        ]
    )
    algorithm_name = "logistic_regression"

    # --- MODEL 2: Linear SVC ---
    # model = Pipeline(
    #     steps=[
    #         ("tfidf", TfidfVectorizer(max_features=max_features)),
    #         ("clf", LinearSVC(C=c_value, random_state=random_state)),
    #     ]
    # )
    # algorithm_name = "linear_svc"

    # --- MODEL 3: Multinomial Naive Bayes ---
    # model = Pipeline(
    # steps=[
    #      ("tfidf", TfidfVectorizer(max_features=max_features)),
    #       ("clf", MultinomialNB()),
    #    ]
    # )
    # algorithm_name = "multinomial_nb"

    # --- MODEL 4: Random Forest ---
    # model = Pipeline(
    #   steps=[
    #      ("tfidf", TfidfVectorizer(max_features=max_features)),
    #     (
    #        "clf",
    #       RandomForestClassifier(
    #          n_estimators=200,
    #         random_state=random_state,
    #        class_weight="balanced",
    #       n_jobs=-1,
    #  ),
    # ),
    # ]
    # )
    # algorithm_name = "random_forest"

    return model, algorithm_name


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
):
    print("\nLoading dataset...")
    df = pd.read_csv(input_path)

    print(f"Dataset size: {len(df)} samples")

    X_train, X_test, y_train, y_test = train_test_split(
        df["prompt"],
        df["label"],
        test_size=test_size,
        random_state=random_state,
        stratify=df["label"],
    )

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()

    # Robust experiment handling
    exp = client.get_experiment_by_name(experiment_name)
    if exp:
        if exp.lifecycle_stage == "deleted":
            print(f"Restoring deleted experiment: {experiment_name}")
            client.restore_experiment(exp.experiment_id)
    else:
        mlflow.create_experiment(experiment_name)

    mlflow.set_experiment(experiment_name)

    model, algorithm_name = build_model(random_state, max_features, c_value)

    print(f"\nTraining model: {algorithm_name}")

    with mlflow.start_run(run_name=f"train_{algorithm_name}") as run:
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        metrics = _compute_metrics(y_test, preds)

        print("Metrics:", metrics)

        mlflow.log_params(
            {
                "algorithm": algorithm_name,
                "random_state": random_state,
                "max_features": max_features,
                "c_value": c_value,
            }
        )

        mlflow.log_metrics(metrics)

        # Log and Register model WITHIN the run block to fix artifact warnings
        model_info = mlflow.sklearn.log_model(
            sk_model=model, artifact_path="model", registered_model_name=registry_model_name
        )

        print("Run ID:", run.info.run_id)
        new_version = model_info.registered_model_version

    # Save local artifacts
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    pd.DataFrame([metrics]).to_json(metrics_path, orient="records", indent=2)

    print(f"\nModel registered as version: {new_version}")

    # Set metadata tag for the version
    client.set_model_version_tag(
        name=registry_model_name,
        version=new_version,
        key="algorithm",
        value=algorithm_name,
    )

    # --- PROMOTION LOGIC (Modern Aliases) ---
    promote = True

    try:
        # Check if a "champion" model already exists
        champion_version = client.get_model_version_by_alias(registry_model_name, "champion")

        # Get metrics for the champion
        champ_run = mlflow.get_run(champion_version.run_id)
        old_f1 = champ_run.data.metrics.get("f1", 0)
        new_f1 = metrics["f1"]

        print(f"\nCurrent Champion F1: {old_f1}")
        print(f"New Model F1: {new_f1}")

        if new_f1 <= old_f1:
            promote = False
            print("New model is NOT better. Keeping current Champion.")
    except mlflow.exceptions.RestException:
        # This occurs if the alias "champion" doesn't exist yet (first run)
        print("No existing Champion found. This is our first leader!")

    if promote:
        print(f"Promoting model version {new_version} to 'champion' alias...")
        client.set_registered_model_alias(
            name=registry_model_name, alias="champion", version=str(new_version)
        )
        print("Model promoted successfully.")
    else:
        print(f"Model version {new_version} remains a challenger.")

    return metrics


# ... existing imports ...

if __name__ == "__main__":
    # Load parameters from params.yml
    with open("params.yml", "r") as f:
        params = yaml.safe_load(f)

    train_and_log(
        input_path=Path(params["data"]["processed_path"]),
        model_path=Path(params["model"]["path"]),
        metrics_path=Path(params["model"]["metrics_path"]),
        tracking_uri=params["mlflow"]["tracking_uri"],
        experiment_name=params["mlflow"]["experiment_name"],
        random_state=params["training"]["random_state"],
        test_size=params["training"]["test_size"],
        max_features=params["training"]["max_features"],
        c_value=params["training"]["c_value"],
        registry_model_name=params["model"]["registry_name"],
    )
