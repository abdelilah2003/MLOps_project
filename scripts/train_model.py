from pathlib import Path
from prompt_firewall.config import load_params
from prompt_firewall.train import train_and_log


if __name__ == "__main__":
    params = load_params()
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
        selection_metric=params["training"]["selection_metric"],
    )
