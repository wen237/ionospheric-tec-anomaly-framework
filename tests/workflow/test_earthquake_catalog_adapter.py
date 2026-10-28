"""Synthetic CSV contracts for the USGS adapter and earthquake selector.

These tests exercise existing validation and UTC calendar-date behavior; they
do not impose physical magnitude bounds or a stricter timestamp grammar.
"""

import csv
from datetime import date

import numpy as np
import pytest

from src.statistical_clustering.earthquake_samples import (
    select_earthquake_samples,
)
from src.workflow.earthquake_catalog_adapter import (
    EarthquakeCatalog,
    load_usgs_earthquake_csv,
)


COLUMNS = ("event_id", "time_utc", "magnitude")
VALID_ROW = ("us-valid", "2000-06-01T12:00:00Z", "6.2")


def write_catalog(tmp_path, rows, *, columns=COLUMNS, encoding="utf-8"):
    path = tmp_path / "catalog.csv"
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)
    return path


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "str"])
def test_preserves_ids_magnitudes_and_input_order(tmp_path, as_string):
    # Unsorted dates, a sub-threshold event, and two events on one UTC date
    # must survive loading: selection belongs to the downstream selector.
    path = write_catalog(
        tmp_path,
        [
            ("us-z", "2000-06-02T12:00:00Z", "6.25"),
            ("us-a", "2000-02-15T00:00:00Z", "5.9"),
            ("us-m", "2000-06-02T01:00:00Z", "7.125"),
        ],
    )

    catalog = load_usgs_earthquake_csv(str(path) if as_string else path)

    assert isinstance(catalog, EarthquakeCatalog)
    assert catalog.event_ids == ("us-z", "us-a", "us-m")
    np.testing.assert_array_equal(
        catalog.event_dates,
        [date(2000, 6, 2), date(2000, 2, 15), date(2000, 6, 2)],
    )
    np.testing.assert_array_equal(catalog.magnitudes, [6.25, 5.9, 7.125])
    assert catalog.event_dates.shape == catalog.magnitudes.shape == (3,)
    assert catalog.event_dates.dtype == np.dtype(object)
    assert all(type(value) is date for value in catalog.event_dates)
    assert catalog.magnitudes.dtype == np.dtype(np.float64)


@pytest.mark.parametrize(
    "timestamp,expected_date",
    [
        ("2000-06-01T23:59:59Z", date(2000, 6, 1)),
        ("2000-06-01T00:00:00+00:00", date(2000, 6, 1)),
        ("2000-06-01T23:59:59-00:00", date(2000, 6, 1)),
        ("2000-06-01T12:30:00+05:30", date(2000, 6, 1)),
        ("2000-06-01T00:15:00+05:30", date(2000, 5, 31)),
        ("2000-06-01T23:45:00-03:30", date(2000, 6, 2)),
        ("2000-01-01T00:30:00+01:00", date(1999, 12, 31)),
        ("2000-12-31T23:30:00-01:00", date(2001, 1, 1)),
        ("2000-03-01T00:00:00.123456+01:00", date(2000, 2, 29)),
    ],
    ids=[
        "z",
        "utc-offset",
        "negative-zero-offset",
        "same-day-offset",
        "previous-day",
        "next-day",
        "previous-year",
        "next-year",
        "leap-day",
    ],
)
def test_converts_aware_timestamps_to_utc_dates(tmp_path, timestamp, expected_date):
    path = write_catalog(tmp_path, [("us-time", timestamp, "6.0")])

    catalog = load_usgs_earthquake_csv(path)

    assert catalog.event_dates.tolist() == [expected_date]


def test_accepts_reordered_required_columns_and_ignores_extra_columns(tmp_path):
    path = write_catalog(
        tmp_path,
        [("6.2", "unused", "us-extra", "2000-06-01T12:00:00Z")],
        columns=("magnitude", "description", "event_id", "time_utc"),
    )

    catalog = load_usgs_earthquake_csv(path)

    assert catalog.event_ids == ("us-extra",)
    assert catalog.event_dates.tolist() == [date(2000, 6, 1)]
    np.testing.assert_array_equal(catalog.magnitudes, [6.2])


@pytest.mark.parametrize("missing_column", COLUMNS)
def test_rejects_missing_required_column(tmp_path, missing_column):
    columns = tuple(column for column in COLUMNS if column != missing_column)
    row = dict(zip(COLUMNS, VALID_ROW))
    path = write_catalog(
        tmp_path, [[row[column] for column in columns]], columns=columns
    )

    with pytest.raises(ValueError, match="CSV missing columns"):
        load_usgs_earthquake_csv(path)


@pytest.mark.parametrize("event_id", ["", " \t "], ids=["empty", "whitespace"])
def test_rejects_empty_event_id(tmp_path, event_id):
    path = write_catalog(tmp_path, [(event_id, VALID_ROW[1], VALID_ROW[2])])

    with pytest.raises(ValueError, match="Invalid CSV row 2: empty event_id"):
        load_usgs_earthquake_csv(path)


@pytest.mark.parametrize(
    "duplicate_id", ["us-valid", " us-valid\t"], ids=["exact", "trimmed"]
)
def test_rejects_duplicate_ids_even_with_different_dates(tmp_path, duplicate_id):
    path = write_catalog(
        tmp_path,
        [VALID_ROW, (duplicate_id, "2000-06-02T00:00:00Z", "7.0")],
    )

    with pytest.raises(ValueError, match="Duplicate USGS event IDs"):
        load_usgs_earthquake_csv(path)


def test_strips_surrounding_field_whitespace(tmp_path):
    path = write_catalog(
        tmp_path, [(" us-trim\t", " 2000-06-01T12:00:00Z ", " 6.25 ")]
    )

    catalog = load_usgs_earthquake_csv(path)

    assert catalog.event_ids == ("us-trim",)
    assert catalog.event_dates.tolist() == [date(2000, 6, 1)]
    np.testing.assert_array_equal(catalog.magnitudes, [6.25])


@pytest.mark.parametrize(
    "timestamp", ["2000-06-01T12:00:00", "2000-06-01", " 2000-06-01T12:00:00 "]
)
def test_rejects_naive_timestamps(tmp_path, timestamp):
    path = write_catalog(tmp_path, [("us-naive", timestamp, "6.0")])

    with pytest.raises(
        ValueError, match="Invalid CSV row 2: UTC timestamp lacks timezone"
    ):
        load_usgs_earthquake_csv(path)


@pytest.mark.parametrize(
    "timestamp",
    [
        "",
        "not-a-timestamp",
        "2000-02-30T12:00:00Z",
        "2000-06-01T25:00:00Z",
        "2000-06-01T12:00:00+25:00",
    ],
    ids=["empty", "text", "invalid-date", "invalid-hour", "invalid-offset"],
)
def test_rejects_invalid_timestamps_and_reports_row(tmp_path, timestamp):
    path = write_catalog(tmp_path, [VALID_ROW, ("us-bad-time", timestamp, "6.0")])

    # Assert the adapter's error context, not Python-version-specific wording.
    with pytest.raises(ValueError, match="Invalid CSV row 3:"):
        load_usgs_earthquake_csv(path)


@pytest.mark.parametrize("magnitude", ["", " ", "not-a-number", "6,2"])
def test_rejects_invalid_magnitudes_and_reports_row(tmp_path, magnitude):
    path = write_catalog(
        tmp_path, [VALID_ROW, ("us-bad-mag", VALID_ROW[1], magnitude)]
    )

    with pytest.raises(ValueError, match="Invalid CSV row 3:"):
        load_usgs_earthquake_csv(path)


@pytest.mark.parametrize(
    "magnitude", ["NaN", "nan", "inf", "-inf", "Infinity", "1e309"]
)
def test_rejects_nonfinite_magnitudes(tmp_path, magnitude):
    path = write_catalog(tmp_path, [("us-nonfinite", VALID_ROW[1], magnitude)])

    with pytest.raises(ValueError, match="Invalid CSV row 2: non-finite magnitude"):
        load_usgs_earthquake_csv(path)


@pytest.mark.parametrize(
    "contents,message",
    [
        ("", "CSV missing columns"),
        ("\n\n", "CSV missing columns"),
        ("event_id,time_utc,magnitude\n", "Earthquake catalog contains no events"),
        ("event_id,time_utc,magnitude\n\n", "Earthquake catalog contains no events"),
    ],
    ids=["empty-file", "blank-file", "header-only", "header-and-blank-line"],
)
def test_rejects_empty_catalogs(tmp_path, contents, message):
    path = tmp_path / "empty.csv"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_usgs_earthquake_csv(path)


def test_accepts_utf8_bom(tmp_path):
    path = write_catalog(tmp_path, [VALID_ROW], encoding="utf-8-sig")
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")

    catalog = load_usgs_earthquake_csv(path)

    assert catalog.event_ids == ("us-valid",)
    assert catalog.event_dates.tolist() == [date(2000, 6, 1)]
    np.testing.assert_array_equal(catalog.magnitudes, [6.2])


@pytest.mark.parametrize(
    "minimum_magnitude,expected_mask,expected_dates,expected_magnitudes",
    [
        (
            6.0,
            [True, False, True, False, True, False, True],
            [
                date(2000, 12, 1),
                date(2000, 6, 1),
                date(2000, 2, 15),
                date(2000, 6, 3),
            ],
            [6.1, 6.0, 6.1, 6.1],
        ),
        (
            6.1,
            [True, False, False, False, True, False, True],
            [date(2000, 12, 1), date(2000, 2, 15), date(2000, 6, 3)],
            [6.1, 6.1, 6.1],
        ),
    ],
    ids=["existing-threshold", "configured-threshold"],
)
def test_loaded_catalog_is_compatible_with_selector(
    tmp_path, minimum_magnitude, expected_mask, expected_dates, expected_magnitudes
):
    # For this synthetic leap year, 30 observation + 15 reference days give
    # inclusive eligible UTC dates February 15 through December 1.
    path = write_catalog(
        tmp_path,
        [
            ("us-upper", "2000-12-01T23:30:00Z", "6.1"),
            ("us-too-early", "2000-02-15T00:30:00+01:00", "9.0"),
            ("us-at-threshold", "2000-06-01T12:00:00Z", "6.0"),
            ("us-too-late", "2000-12-01T23:30:00-01:00", "9.0"),
            ("us-lower", "2000-02-14T23:30:00-01:00", "6.1"),
            ("us-below-threshold", "2000-06-02T12:00:00Z", "5.9"),
            ("us-above-threshold", "2000-06-03T12:00:00Z", "6.1"),
        ],
    )
    catalog = load_usgs_earthquake_csv(path)

    result = select_earthquake_samples(
        event_dates=catalog.event_dates,
        magnitudes=catalog.magnitudes,
        analysis_start=date(2000, 1, 1),
        analysis_end=date(2000, 12, 31),
        minimum_magnitude=minimum_magnitude,
        observation_days=30,
        reference_days=15,
    )

    np.testing.assert_array_equal(result.selected_mask, expected_mask)
    np.testing.assert_array_equal(result.selected_dates, expected_dates)
    np.testing.assert_array_equal(result.selected_magnitudes, expected_magnitudes)
    np.testing.assert_array_equal(result.event_dates, catalog.event_dates)
    np.testing.assert_array_equal(result.magnitudes, catalog.magnitudes)


def test_valid_catalog_can_have_no_eligible_samples(tmp_path):
    path = write_catalog(tmp_path, [("us-small", VALID_ROW[1], "5.9")])
    catalog = load_usgs_earthquake_csv(path)

    result = select_earthquake_samples(
        catalog.event_dates,
        catalog.magnitudes,
        analysis_start=date(2000, 1, 1),
        analysis_end=date(2000, 12, 31),
    )

    assert catalog.event_ids == ("us-small",)
    np.testing.assert_array_equal(result.selected_mask, [False])
    assert result.selected_dates.shape == result.selected_magnitudes.shape == (0,)
