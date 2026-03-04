from pathlib import Path
from prompt_firewall.config import load_params
from prompt_firewall.data import clean_dataset

if __name__ == "__main__":
    params = load_params()
    clean_dataset(Path(params["data"]["raw_path"]), Path(params["data"]["processed_path"]))
