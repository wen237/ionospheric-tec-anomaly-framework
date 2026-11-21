"""Synthetic exports and optional real-toolkit offline parser integration."""

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.workflow.space_weather_evidence import (
    build_space_weather_report, load_toolkit, prepare_space_weather_report,
    read_exported_csv, validate_space_weather_report,
)


WINDOW = dict(start_utc="2022-05-28T00:00:00Z", end_utc="2022-05-28T02:00:00Z")
CSV = ("datetime_utc,year,doy,hour,kp,kp_x10,dst,f107\n"
       "2022-05-28T00:00:00,2022,148,0,2.7,27,-17,110.6\n"
       "2022-05-28T03:00:00+01:00,2022,148,2,,,0,\n")


@pytest.fixture
def toolkit_contract():
    # Test double of the export contract, not a scientific processing algorithm.
    def record(timestamp, year, doy, hour, values):
        return SimpleNamespace(timestamp=timestamp, year=year, doy=doy, hour=hour, values=values)
    return SimpleNamespace(OMNIRecord=record, VARIABLES={
        "kp": dict(fill_values={"99"}), "dst": dict(fill_values={"99999"}), "f107": dict(fill_values={"999.9"})})


def test_csv_utc_alignment_missing_rows_native_cadence_and_exact_values(toolkit_contract):
    records = read_exported_csv(CSV.encode(), toolkit_contract)
    report = build_space_weather_report(records, WINDOW, case_id="synthetic", provenance={})
    assert report["rows"][0]["values"] == dict(kp=2.7, kp_x10=27.0, dst=-17.0, f107=110.6)
    assert report["rows"][1]["source_row_present"] is False
    assert report["rows"][1]["values"]["dst"] is None
    assert report["rows"][2]["timestamp_utc"] == "2022-05-28T02:00:00Z"
    assert report["rows"][2]["values"]["dst"] == 0.0
    assert report["summary"]["kp"]["available_hourly_rows"] == 1
    assert report["summary"]["kp"]["missing_hourly_rows"] == 2
    assert report["summary"]["kp"]["native_resolution_hours"] == 3
    assert report["summary"]["dst"]["native_resolution_hours"] == 1
    assert report["summary"]["f107"]["native_resolution_hours"] == 24
    assert report == validate_space_weather_report(report)


@pytest.mark.parametrize("old,new", [
    ("2.7,27", "2.7,28"), ("2.7,27", "2.7,"), ("-17", "99999"),
    ("110.6", "999.9"), ("110.6", "nan"), ("2022,148,0", "2022,149,0"),
    ("00:00:00", "00:00:01"), ("kp_x10", "unknown"),
])
def test_invalid_exports_fail_without_silent_conversion(toolkit_contract, old, new):
    with pytest.raises((ValueError, KeyError)):
        read_exported_csv(CSV.replace(old, new).encode(), toolkit_contract)


def test_duplicate_normalized_utc_and_absence_not_zero(toolkit_contract):
    records = read_exported_csv(CSV.encode(), toolkit_contract)
    with pytest.raises(ValueError, match="Duplicate"):
        build_space_weather_report([records[0], records[0]], WINDOW, case_id="synthetic", provenance={})
    report = build_space_weather_report([], WINDOW, case_id="synthetic", provenance={})
    assert report["summary"]["dst"]["maximum"] is None
    assert report["summary"]["dst"]["maximum_utc_hours"] == []
    assert report["absent_utc_rows"] == 3
    altered = deepcopy(report)
    altered["rows"][1]["values"]["kp"] = 0
    with pytest.raises(ValueError):
        validate_space_weather_report(altered)


TOOLKIT = Path(__file__).resolve().parents[3] / "space-weather-data-tools" / "omni_downloader.py"
@pytest.mark.skipif(not TOOLKIT.is_file() or importlib.util.find_spec("requests") is None,
                    reason="Optional sibling toolkit and its requests dependency are required")
def test_original_toolkit_raw_response_and_export_are_equivalent(tmp_path, monkeypatch):
    """Actually call the existing parser, with all network operations prohibited."""
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline adapter attempted network retrieval")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    module, code_pin = load_toolkit(TOOLKIT)
    monkeypatch.setattr(module.OMNIWebDownloader, "retrieve", forbidden)
    source = tmp_path / "synthetic_response.txt"
    source.write_text("<pre>Kp index Dst-index F10.7_index\n2022 148 0 27 -17 110.6\n2022 148 2 99 99999 999.9</pre>", encoding="utf-8")
    raw_report = prepare_space_weather_report(source, TOOLKIT, WINDOW, case_id="synthetic", source_format="omni_response")
    assert raw_report["rows"][0]["values"]["kp"] == 2.7
    assert raw_report["rows"][2]["values"] == dict(kp=None, kp_x10=None, dst=None, f107=None)
    assert raw_report["provenance"]["toolkit"] == code_pin
    assert raw_report["provenance"]["retrieval_performed"] is False
    records = module.OMNIWebDownloader._parse_response(source.read_text(), ["kp", "dst", "f107"])
    csv_path = module.save_csv(records, tmp_path / "synthetic.csv", ["kp", "dst", "f107"])
    csv_report = prepare_space_weather_report(csv_path, TOOLKIT, WINDOW, case_id="synthetic")
    assert raw_report["rows"] == csv_report["rows"]
    assert raw_report["summary"] == csv_report["summary"]
    source.write_text("<pre>Kp index Dst-index\n2022 148 0 27 -17 110.6</pre>", encoding="utf-8")
    with pytest.raises(module.OMNIParseError):
        prepare_space_weather_report(source, TOOLKIT, WINDOW, case_id="synthetic", source_format="omni_response")
