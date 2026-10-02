import os
from pathlib import Path


CODE_GIM_DIR = Path(
    os.environ.get(
        "IONO_CODE_GIM_DIR",
        r"I:/IRSL/CODEGIM_FIN_py",
    )
)

GIMTEC_DATASET_DIR = Path(
    os.environ.get(
        "IONO_GIMTEC_DATASET_DIR",
        r"I:/IRSL/GIMTEC_interpolation_py",
    )
)

AFGHANISTAN_DATA_DIR = (
    GIMTEC_DATASET_DIR / "Afghanistan19990101_20211231"
)

LEGACY_TEC_PATH = (
    AFGHANISTAN_DATA_DIR / "tec33.092_69.514.npy"
)

EQLIST_PATH = (
    AFGHANISTAN_DATA_DIR / "eqlist.npy"
)