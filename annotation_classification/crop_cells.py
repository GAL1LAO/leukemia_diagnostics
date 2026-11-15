from pathlib import Path
from typing import Any

from wsi2sc.config import config_from_dict
from wsi2sc.pipeline import run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
DICOM_IMAGE_DIR = (
    REPO_ROOT
    / "_data"
    / "bonemarrowwsi_pediatricleukemia"
    / "A6BBC91AE73DD21C0533F735470A9CD0"
    / "MS"
)

config = {
    "data": {
        "input_path": str(DICOM_IMAGE_DIR),
        "input_format": "dicom",
        "mode": "single",
    },
    "monolayer_filter": {"type": "brightness", "enabled": True},
    "detection": {
        "model": "nca",
        "target_mpp": 0.97,
        "device": "auto",
    },
    "cell_processing": {
        "patch_size": 192,
        "quality": {"enabled": True, "threshold": 0.5},
        "features": {"enabled": False},
    },
    "output": {
        "dir": str(REPO_ROOT / "outputs" / "wsi2sc"),
        "skip_existing": True,
    },
}


def run_crop_cells_pipeline(config: dict[str, Any]) -> None:
    """Run the crop_cells pipeline with the given configuration."""
    # Load the configuration
    cfg = config_from_dict(config)

    # Run the pipeline
    return run_pipeline(cfg)


if __name__ == "__main__":
    run_crop_cells_pipeline(config)
    print(f"Saved outputs to {REPO_ROOT / 'outputs' / 'wsi2sc'}")
