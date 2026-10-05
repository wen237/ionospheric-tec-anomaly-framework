"""Shared configuration for Afghanistan temporal-anomaly validation."""

from datetime import datetime
import os
from pathlib import Path


# Afghanistan earthquake epicenter
LATITUDE = 33.020
LONGITUDE = 69.464

# Full 46-day TEC input period
START_TIME = datetime(
    2022,
    5,
    7,
    0,
    0,
)

END_TIME = datetime(
    2022,
    6,
    21,
    23,
    0,
)

CASE_END_DATE = datetime(
    2022,
    6,
    21,
)

# Temporal anomaly parameters
REFERENCE_DAYS = 15
THRESHOLD_MULTIPLIER = 3.0


# ==========================================================
# Local validation data
# ==========================================================

PROCESSED_DIR = Path(
    os.environ.get(
        "TEC_PROCESSED_DIR",
        "processed",
    )
)

LEGACY_GIM_DIR = Path(
    os.environ.get(
        "TEC_LEGACY_GIM_DIR",
        "legacy_gim",
    )
)

LEGACY_TEC_FILE = Path(
    os.environ.get(
        "TEC_LEGACY_TEC_FILE",
        "old_tec.npz",
    )
)

NEW_TEC_FILE = Path(
    os.environ.get(
        "TEC_NEW_TEC_FILE",
        "afghanistan_new_tec_validation.npz",
    )
)