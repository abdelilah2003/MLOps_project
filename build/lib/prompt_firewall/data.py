from pathlib import Path
import pandas as pd


REQUIRED_COLUMNS = {"prompt", "label"}


def clean_dataset(input_path: Path, output_path: Path) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    # Allow alternative user format "prompt,1 or 0" then normalize.
    if "1 or 0" in df.columns:
        df = df.rename(columns={"1 or 0": "label"})
    if not REQUIRED_COLUMNS.issubset(df.columns):
        raise ValueError(f"Dataset must contain columns {REQUIRED_COLUMNS}")
    df = df[["prompt", "label"]].dropna()
    df["prompt"] = df["prompt"].astype(str).str.strip()
    df = df[df["prompt"].str.len() > 0]
    df["label"] = df["label"].astype(int)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df
