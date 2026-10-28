"""Reproduce historical Afghanistan B+C from the original saved hourly TEC.

Run from the repository root with ``python -m
examples.reproduce_afghanistan_historical_bc --help``. No GIM reconstruction
or new TEC interpolation is performed. NPY timestamps are assigned according
to the Legacy UTC convention; they are not embedded observations.
"""

import argparse
from dataclasses import asdict
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np

from src.statistical_clustering.reproducibility import get_clustering_environment
from src.workflow.clustering_adapter import run_clustering_workflow
from src.workflow.earthquake_catalog_adapter import load_usgs_earthquake_csv
from src.workflow.historical_input_adapter import prepare_historical_daily_tec
from src.workflow.statistical_analysis_adapter import run_statistical_analysis
from src.workflow.statistical_significance_adapter import run_statistical_significance


START = date(1999, 1, 1)
END = date(2021, 12, 31)
N_DAYS = (END - START).days + 1
N_HOURS = N_DAYS * 24
OUTPUT_NAME = "afghanistan_historical_bc_summary.json"
CONFIG = dict(
    minimum_magnitude=6.0, observation_days=30, reference_days=15,
    threshold_multiplier=3.0,
)


def _input_record(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return dict(path=str(path), size_bytes=path.stat().st_size, sha256=digest.hexdigest())


def _load_npy(path):
    # Check the container before loading; never enable object deserialization.
    with path.open("rb") as handle:
        np.lib.format.read_magic(handle)
    array = np.load(path, mmap_mode="r", allow_pickle=False)
    if array.dtype.kind not in "fiu" or not np.all(np.isfinite(array)):
        raise ValueError(f"NPY must contain only finite real numeric values: {path}")
    return array


def _run_bc(historical, dates, magnitudes):
    analysis = run_statistical_analysis(historical, dates, magnitudes, **CONFIG)
    significance = run_statistical_significance(analysis, critical_z=1.96)
    clustering = run_clustering_workflow(
        significance, observation_days=30, n_clusters=2, random_state=42,
    )
    return analysis, significance, clustering


def _window_summary(significance, rows):
    days = significance.relative_days[rows]
    mask = significance.significance_mask[rows]
    overlap = significance.overlap_mask[rows]
    return dict(
        relative_day_start=int(days[0]), relative_day_end=int(days[-1]),
        shape=list(mask.shape),
        positive_significant_count=int(significance.positive_significant[rows].sum()),
        negative_significant_count=int(significance.negative_significant[rows].sum()),
        positive_mask_count=int(np.count_nonzero(mask == 1)),
        negative_mask_count=int(np.count_nonzero(mask == -1)),
        zero_mask_count=int(np.count_nonzero(mask == 0)),
        nonzero_mask_count=int(np.count_nonzero(mask)),
        overlap_count=int(overlap.sum()),
        significant_cells=[
            dict(relative_day=int(days[r]), hour_utc=int(h), polarity=int(mask[r, h]))
            for r, h in np.argwhere(mask != 0)
        ],
        overlap_cells=[
            dict(relative_day=int(days[r]), hour_utc=int(h),
                 positive_z=float(significance.z_test.positive_z[rows][r, h]),
                 negative_z=float(significance.z_test.negative_z[rows][r, h]))
            for r, h in np.argwhere(overlap)
        ],
    )


def _reference_comparison(analysis, workflow):
    # Documented references, not fitted targets or input acceptance criteria.
    expected = dict(
        selected_events=74, pre_event_cells=34, positive_cells=18, negative_cells=16,
        positive_anchor_days=[-8], negative_anchor_days=[-22],
        silhouette=0.31105623341145205,
    )
    actual = dict(
        selected_events=analysis.n_events,
        pre_event_cells=workflow.n_significant_cells,
        positive_cells=int(np.count_nonzero(workflow.clustering_mask == 1)),
        negative_cells=int(np.count_nonzero(workflow.clustering_mask == -1)),
        positive_anchor_days=sorted(a.rounded_day for a in workflow.clustering.temporal_anchors
                                   if a.dominant_polarity == 1),
        negative_anchor_days=sorted(a.rounded_day for a in workflow.clustering.temporal_anchors
                                   if a.dominant_polarity == -1),
        silhouette=workflow.clustering.kmeans.silhouette,
    )
    checks = {
        name: dict(expected=value, actual=actual[name], matches=(
            bool(np.isclose(actual[name], value, rtol=0, atol=1e-12))
            if name == "silhouette" else actual[name] == value
        ))
        for name, value in expected.items()
    }
    return dict(
        source="docs/agent_handoff.md; tests/regression/afghanistan_clustering_reference.py",
        silhouette_atol=1e-12, checks=checks,
        all_match=all(check["matches"] for check in checks.values()),
    )


def _array_comparison(left, right):
    left, right = np.asarray(left), np.asarray(right)
    result = dict(equal=bool(np.array_equal(left, right)))
    if left.shape == right.shape and np.issubdtype(left.dtype, np.number):
        result.update(
            differing_values=int(np.count_nonzero(left != right)),
            max_abs_difference=float(np.max(np.abs(left - right))) if left.size else 0.0,
        )
    return result


def _legacy_comparison(current, legacy, dates, magnitudes, catalog):
    analysis, significance, workflow = current
    other, other_sig, other_workflow = legacy
    selected, other_selected = analysis.earthquake_samples, other.earthquake_samples
    order, other_order = np.argsort(selected.selected_dates), np.argsort(other_selected.selected_dates)
    checks = dict(all_catalog_date_magnitude_pairs=dict(equal=(
        sorted(zip(catalog.event_dates, catalog.magnitudes)) == sorted(zip(dates, magnitudes))
    )))
    checks["selected_dates"] = _array_comparison(
        selected.selected_dates[order], other_selected.selected_dates[other_order],
    )
    checks["selected_magnitudes"] = _array_comparison(
        selected.selected_magnitudes[order], other_selected.selected_magnitudes[other_order],
    )
    for field in vars(analysis.population):
        checks["population." + field] = _array_comparison(
            getattr(analysis.population, field), getattr(other.population, field),
        )
    for field in ("positive_counts", "negative_counts"):
        checks["subset." + field] = _array_comparison(
            getattr(analysis.earthquake_subset, field), getattr(other.earthquake_subset, field),
        )
    checks["subset.delta_tec"] = (
        _array_comparison(analysis.earthquake_subset.delta_tec[:, :, order],
                          other.earthquake_subset.delta_tec[:, :, other_order])
        if checks["selected_dates"]["equal"] else
        dict(equal=None, reason="Cannot align delta_tec: selected UTC dates differ.")
    )
    for field in ("positive_z", "negative_z"):
        checks["z_test." + field] = _array_comparison(
            getattr(significance.z_test, field), getattr(other_sig.z_test, field),
        )
    for field in ("significance_mask", "overlap_mask"):
        checks[field] = _array_comparison(getattr(significance, field), getattr(other_sig, field))
    c, other_c = workflow.clustering, other_workflow.clustering
    for label, left, right in (
        ("clustering.raw_features", c.clustering_features.raw_features, other_c.clustering_features.raw_features),
        ("clustering.standardized_features", c.scaled_features.standardized_features, other_c.scaled_features.standardized_features),
        ("clustering.labels", c.kmeans.labels, other_c.kmeans.labels),
        ("clustering.centers", c.kmeans.centers, other_c.kmeans.centers),
        ("clustering.decoded_centers", c.decoded_centroids.decoded_centers, other_c.decoded_centroids.decoded_centers),
        ("clustering.silhouette", c.kmeans.silhouette, other_c.kmeans.silhouette),
    ):
        checks[label] = _array_comparison(left, right)
    return dict(
        n_catalog_events=len(dates), n_selected_events=other.n_events,
        event_alignment="UTC calendar date",
        all_match=all(check["equal"] is True for check in checks.values()),
        first_difference=next((name for name, check in checks.items() if check["equal"] is False), None),
        checks=checks,
    )


def _write_summary_atomic(output, text, *, overwrite):
    """Publish a complete same-filesystem file, without clobber by default.

    Hard-link creation is atomic and fails if the destination already exists.
    Filesystems without hard-link support fail closed; no unsafe fallback is
    used. Close the temporary file before publication for Windows compatibility.
    """
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=f".{output.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, output)
        else:
            os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def reproduce(tec_path, catalog_path, output_dir, *, legacy_path=None, overwrite=False):
    """Run fixed-configuration B+C and save one strict JSON summary.

    A reference mismatch is recorded, not corrected or treated as invalid input.
    Only an explicit overwrite=True authorizes replacing an existing summary.
    """
    paths = dict(tec=Path(tec_path).resolve(strict=True), usgs_catalog=Path(catalog_path).resolve(strict=True))
    if legacy_path is not None:
        paths["legacy_catalog"] = Path(legacy_path).resolve(strict=True)
    output = Path(output_dir).resolve() / OUTPUT_NAME
    for path in paths.values():
        if output.resolve() == path or (output.exists() and output.samefile(path)):
            raise ValueError("The summary output must not replace an input file.")
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {output}; use --overwrite to authorize replacement.")
    inputs = {name: _input_record(path) for name, path in paths.items()}
    raw = _load_npy(paths["tec"])
    if raw.shape not in ((N_HOURS,), (N_HOURS, 1), (N_DAYS, 24)):
        raise ValueError(f"TEC must have {N_HOURS} hourly samples in chronological order; got {raw.shape}.")
    flat = raw.reshape(-1)
    epochs = np.asarray([datetime(1999, 1, 1) + timedelta(hours=i) for i in range(N_HOURS)], dtype=object)
    historical = prepare_historical_daily_tec(
        epochs, flat, start_date=START, end_date=END, allow_interpolation=False,
    )
    prepared = historical.daily_tec.reshape(-1)
    # Also round-trip the dtype: uint64/float64 equality alone can hide rounding.
    unchanged = bool(np.array_equal(flat, prepared)
                     and np.array_equal(flat, prepared.astype(flat.dtype)))
    if not unchanged or historical.hourly_result.interpolated_mask.any():
        raise ValueError("TEC values changed or required interpolation.")
    catalog = load_usgs_earthquake_csv(paths["usgs_catalog"])
    if len(set(catalog.event_dates)) != len(catalog.event_dates):
        raise ValueError("The filtered catalog must contain one representative per UTC date.")
    legacy_dates = legacy_magnitudes = None
    if legacy_path is not None:
        eqlist = _load_npy(paths["legacy_catalog"])
        if eqlist.ndim != 2 or eqlist.shape[1] != 10 or not len(eqlist):
            raise ValueError("Legacy eqlist must have shape (n_events, 10).")
        if not np.all(eqlist[:, :3] == np.floor(eqlist[:, :3])):
            raise ValueError("Legacy year/month/day columns must contain integers.")
        legacy_dates = np.asarray([date(*(int(v) for v in row[:3])) for row in eqlist], dtype=object)
        if len(set(legacy_dates)) != len(legacy_dates):
            raise ValueError("Legacy eqlist must contain one representative per UTC date.")
        legacy_magnitudes = eqlist[:, -1]
    current = _run_bc(historical, catalog.event_dates, catalog.magnitudes)
    analysis, significance, workflow = current
    c = workflow.clustering
    subset = analysis.earthquake_subset
    summary = dict(
        summary_type="afghanistan_historical_bc_reproduction", schema_version=1,
        inputs=inputs,
        configuration=dict(start_date=START.isoformat(), end_date=END.isoformat(), **CONFIG,
                           critical_z=1.96, clustering_days=[-30, 0], n_clusters=2, random_state=42),
        environment=asdict(get_clustering_environment(n_clusters=2, random_state=42)),
        historical_data=dict(
            input_shape=list(raw.shape), input_dtype=str(raw.dtype),
            daily_shape=list(historical.daily_tec.shape), n_days=historical.n_days, n_hours=N_HOURS,
            assigned_start_utc=epochs[0].isoformat() + "Z", assigned_end_utc=epochs[-1].isoformat() + "Z",
            timeline_provenance="Assigned Legacy UTC hourly timeline; NPY has no embedded timestamps.",
            finite_count=int(np.isfinite(flat).sum()), nan_count=0, infinite_count=0,
            minimum=float(flat.min()), maximum=float(flat.max()),
            observed_input_count=int(historical.hourly_result.observed_mask.sum()),
            interpolated_count=int(historical.hourly_result.interpolated_mask.sum()), values_unchanged=unchanged,
        ),
        population_baseline=asdict(analysis.population),
        earthquake_selection=dict(
            n_catalog_events=len(catalog.event_dates), n_selected_events=analysis.n_events,
            events=[dict(date=d.isoformat(), magnitude=float(m), event_id=event_id)
                    for d, m, event_id, keep in zip(catalog.event_dates, catalog.magnitudes,
                                                  catalog.event_ids, analysis.earthquake_samples.selected_mask) if keep],
        ),
        earthquake_subset=dict(
            counts_shape=list(subset.positive_counts.shape), delta_tec_shape=list(subset.delta_tec.shape),
            positive_count=int(subset.positive_counts.sum()), negative_count=int(subset.negative_counts.sum()),
            positive_count_range=[int(subset.positive_counts.min()), int(subset.positive_counts.max())],
            negative_count_range=[int(subset.negative_counts.min()), int(subset.negative_counts.max())],
        ),
        statistical_significance=dict(
            full_window=_window_summary(significance, np.ones(len(significance.relative_days), dtype=bool)),
            pre_event=_window_summary(significance, significance.relative_days <= 0),
        ),
        clustering=dict(
            window_selection="pre_event", relative_days=workflow.clustering_relative_days.tolist(),
            n_significant_cells=workflow.n_significant_cells,
            raw_features=c.clustering_features.raw_features.tolist(),
            feature_shape=list(c.clustering_features.features.shape),
            standardized_feature_shape=list(c.scaled_features.standardized_features.shape),
            standardized_centers=c.kmeans.centers.tolist(),
            decoded_centers=c.decoded_centroids.decoded_centers.tolist(),
            rounded_centers=c.centroid_presentation.rounded_centers.tolist(),
            temporal_anchors=[asdict(anchor) for anchor in c.temporal_anchors],
            silhouette=c.kmeans.silhouette, inertia=c.kmeans.inertia,
        ),
        reference_comparison=_reference_comparison(analysis, workflow),
        legacy_comparison=None,
    )
    if legacy_path is not None:
        legacy = _run_bc(historical, legacy_dates, legacy_magnitudes)
        summary["legacy_comparison"] = _legacy_comparison(
            current, legacy, legacy_dates, legacy_magnitudes, catalog,
        )
    for name, path in paths.items():
        if _input_record(path) != inputs[name]:
            raise ValueError(f"Input changed during execution: {path}")
    summary["input_integrity_verified_after_run"] = True
    text = json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_summary_atomic(output, text, overwrite=overwrite)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tec", type=Path, required=True, help="Original saved historical TEC NPY.")
    parser.add_argument("--catalog", type=Path, required=True, help="Filtered USGS earthquake CSV.")
    parser.add_argument("--legacy-eqlist", type=Path, help="Optional Legacy numeric earthquake NPY.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true", help="Explicitly authorize summary replacement.")
    args = parser.parse_args(argv)
    try:
        output = reproduce(args.tec, args.catalog, args.output_dir,
                           legacy_path=args.legacy_eqlist, overwrite=args.overwrite)
    except FileExistsError as exc:
        parser.exit(3, f"Output conflict: {exc}\n")
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"Reproduction failed: {exc}\n")
    print(f"Saved historical B+C summary: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
