from pathlib import Path
import pandas as pd
from evidently import ColumnMapping
from evidently.metric_preset import DataDriftPreset, DataQualityPreset
from evidently.report import Report


def build_monitoring_report(reference_path: Path, current_path: Path, output_path: Path) -> None:
    reference = pd.read_csv(reference_path)
    current = pd.read_csv(current_path)

    mapping = ColumnMapping(target="label", text_features=["prompt"])
    report = Report(metrics=[DataDriftPreset(), DataQualityPreset()])
    report.run(reference_data=reference, current_data=current, column_mapping=mapping)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report.save_html(str(output_path))
