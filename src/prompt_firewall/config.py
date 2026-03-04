from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
PARAMS_PATH = ROOT / "params.yaml"


def load_params(path: Path = PARAMS_PATH) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
