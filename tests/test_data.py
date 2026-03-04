from pathlib import Path
from prompt_firewall.data import clean_dataset


def test_clean_dataset(tmp_path: Path):
    raw = tmp_path / "raw.csv"
    out = tmp_path / "clean.csv"
    raw.write_text("prompt,1 or 0\nHello,0\nHack,1\n", encoding="utf-8")

    df = clean_dataset(raw, out)

    assert out.exists()
    assert list(df.columns) == ["prompt", "label"]
    assert df["label"].tolist() == [0, 1]
