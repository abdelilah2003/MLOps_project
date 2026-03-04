from pathlib import Path
from prompt_firewall.config import load_params
from prompt_firewall.monitor import build_monitoring_report


if __name__ == "__main__":
    params = load_params()
    build_monitoring_report(
        reference_path=Path(params["monitoring"]["reference_data_path"]),
        current_path=Path(params["monitoring"]["current_data_path"]),
        output_path=Path(params["monitoring"]["report_path"]),
    )
