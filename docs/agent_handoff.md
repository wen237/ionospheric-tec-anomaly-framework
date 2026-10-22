# AI agent handoff — Afghanistan TEC research reproduction

**Status date:** 2026-10-22. This is a handoff of verified work and outstanding work, not a claim that remaining analyses have been run.

## Mission and current decision

Complete reproducible end-to-end Afghanistan Framework B+C using the researcher's **original saved 1999–2021 hourly historical TEC**, and develop a modest researcher-reviewed A/B+C-to-D candidate-window workflow. **Do not require the newly downloaded 23-year CODE GIM data.** The researcher has explicitly discontinued that download/reconstruction plan. Retain existing modern historical reconstruction code as an optional scientific utility; do not delete or retrofit it unless separately requested.

Existing independent framework implementations and Legacy comparison tests must remain intact. Modern 2022 Framework A and D examples already work; focus on integrating these inputs and outputs cleanly, not rewriting scientific computation.

## Verified results versus unfinished results

| Area | Observed verification | What remains |
|---|---|---|
| Framework A, 2022 Afghanistan | Modern CODE GIM reproduces 744 hourly anomalies: 37 positive, 610 normal, 97 negative. | Preserve implementation; daily evidence can inform candidate selection. |
| Framework A negative episode | 2022-05-28 through 2022-06-01 negative hours: **18, 16, 24, 20, 17** (95 of 120 hours). | Define a transparent, non-post-hoc candidate-selection rule before generalizing. |
| Historical USGS catalog | Fresh query: 922 initial events; analysis-window filter: 917; one daily max: 741. Compared to Legacy: 741 matching UTC dates and magnitudes; 4 coordinate differences. Framework B+C selector returns 74 M>=6.0 eligible events, same dates as Legacy; first 1999-03-04, last 2021-11-14. | Connect CSV to end-to-end original-TEC analysis. Preserve evidence of four location changes. |
| Framework B+C algorithms | Existing tested statistical/clustering components and Legacy test data / validations reside in repo. Published Afghanistan reference: **74 events; 34 pre-event significant cells (18 positive, 16 negative); k=2 anchors Day -8 positive and Day -22 negative.** | End-to-end run with original historical TEC and modern catalog; check 31-day pre-event mask rather than accidentally clustering the entire ±30-day window. |
| Modern historical GIM reconstruction | 1999-01-01 to 1999-01-07 test: 84 two-hour measurements -> 168 hourly samples, no NaNs; initial values 6.30, 6.30, 12.35, 18.40, 24.90, with Pandas `method="time"`, `limit_direction="both"`. | **No longer needed for this project's required B+C reproduction.** |
| Framework D, 2022 Afghanistan | Verified 20 daily modern NPZ files, 2022-05-13 through 2022-06-01; window 2022-05-28 00:00 to 2022-06-01 23:00 UTC, 15 reference days, k=3; 120 target hours; 5183 finite cells; positive peak 10% at (-22.5,-155), (-22.5,-150); negative peak 85% at (30,70). All six reported numerical checks PASS. | Full plot visual checked by researcher after correcting upside-down modern latitude, clipping, and adding coastline/borders. Preserve. End-to-end Stage 2 Modern path is not yet integrated. |
| Git | A recent checkpoint committed revised Modern spatial plot, summary, and examples, per researcher. | Re-run repository tests before accepting new agent changes. |

## Relevant repositories and files

- `wen237/ionospheric-tec-anomaly-framework` — main scientific repository, primary agent work.
- `wen237/earthquake-data-tools` — `usgs_downloader.py` and `earthquake_filter.py` created the verified earthquake CSV. **Do not reimplement retrieval/filtering here.**
- `wen237/gim-data-tools` — full-global GIM download/conversion; **not an active dependency for rebuilding 1999–2021 TEC in this project.** Previously downloaded 2022 daily NPZ can still be used for Framework A/D reproduction.

Principal scientific code:
- `src/workflow/earthquake_catalog_adapter.py` — read filtered USGS CSV as `event_dates`, `magnitudes`.
- `src/statistical_clustering/earthquake_samples.py`, `src/workflow/statistical_analysis_adapter.py`, `src/workflow/statistical_significance_adapter.py`, `src/workflow/clustering_adapter.py` — use, don't rewrite.
- `src/workflow/historical_input_adapter.py` — validates full 1999–2021 daily/hourly inputs. Original historical TEC may be a 1D NPY with 201624 values, to be reshaped to (8401,24) under an explicit UTC timeline.
- `src/workflow/modern_historical_reconstruction.py` — optional archival utility; do not make it the required path.
- `validation/statistical_clustering/` — verified Legacy comparisons, catalog config paths, real-data algorithms.
- `src/workflow/modern_spatial_input_adapter.py` — validated Modern Framework D scientific computation.
- `src/spatial_verification/spatial_plot.py`, `src/workflow/spatial_summary_export.py` — corrected orientation/presentation; inspect current `grid_orientation` argument and don't regress Modern's ascending-latitude convention.
- `src/workflow/stage2_cli.py` and `src/workflow/stage2_runner.py` — existing Legacy-oriented explicit Stage 2 interface; any Modern extension must be opt-in, not break Legacy.
- `src/workflow/preparation_manifest.py`, `src/workflow/clustering_summary.py` — existing metadata contracts; reuse.

User-held reference paths (might not exist in an agent's runtime):
```text
I:\IRSL\GIMTEC_interpolation_py\Afghanistan19990101_20211231\tec33.092_69.514.npy
I:\IRSL\GIMTEC_interpolation_py\Afghanistan19990101_20211231\eqlist.npy
C:\Users\Wen\Documents\GitHub\earthquake-data-tools\afghanistan_usgs_filtered.csv
C:\Users\Wen\Documents\GitHub\gim-data-tools\processed\
```
Do not hard-code local paths in production code. Use CLI arguments/environment configuration. Request user-provided original files when they are not mounted; do not fabricate or infer their content from outputs.

## Remaining work, ordered by dependency

### 1. Historical B+C using original data

1. Inspect original NPY shape/dtype, UTC coverage (1999-01-01 00:00 through 2021-12-31 23:00), finite values, and known edge fill policy; validate against expected 8401 days, 201624 hours without mutating original.
2. Load verified filtered USGS CSV through the current adapter; check exact event counts and valid date bounds. Compare selected dates with Legacy `eqlist.npy`.
3. Reuse production `run_statistical_analysis`, `run_statistical_significance`, `run_statistical_clustering` or clustering adapter as their contracts permit. In particular, inspect the existing ±30-day mask and restrict the paper-reproduction clustering to the **pre-event relative days -30..0** where scientifically required.
4. Report all actual values: selected events, population rates, polarity-specific significant cells, positive and negative anchor dates, numerical comparison to Legacy; do not silently adjust data to force reference values.
5. Add a narrowly scoped Afghanistan reproduction CLI/example and validation tests. Avoid duplicate core modules, unnecessary exporters or extra data files.

**Accept if:** real original TEC + modern catalog runs reproducibly, all expected scientific comparisons documented, failures explained. Counts and anchors match reference only if the execution actually demonstrates it.

### 2. Candidate-window report, then researcher sign-off

1. Read Framework A's hourly anomaly classifications. For the verified five-day period, the negative counts are 18/16/24/20/17; do not assume this exact interval is a universally applicable threshold or model.
2. Once B+C is produced, supply polarities, significant relative-day/hour cells, and clustering anchors as *evidence*, not unquestioned dates. Report candidate start/end UTC, reason, TEC coverage, and scientific limitations.
3. Propose an explicit, configurable window-selection policy; test ambiguous or multiple candidates. **Do not automatically label anomalies as seismic precursors.**
4. Keep Stage 2's explicit researcher confirmation before running or claiming spatial verification.

**Accept if:** given same synthetic/frozen input, candidate list is deterministic and explanation/UTC bounds are reproducible; researcher can override selection.

### 3. Modern Stage 2 integration

Existing `stage2_cli` primarily goes through Legacy `spatial_adapter`. Add an **explicit Modern opt-in** for GIM NPZ file/dataset paths that preserves the existing CLI contract and scientific computation. Reuse corrected plots and summaries, retain complete original output metadata and no-overwrite protections. Do not silently change Legacy behavior.

**Accept if:** Modern Afghanistan case reproduces 120h/71x73/10%/85%/peak coordinates, Modern plotted/JSON latitudes agree, and old Legacy Stage 2 and regression tests still pass.

### 4. Testing, documentation, and delivery

- Run `python -m pytest tests -q` when dependencies are available and record the actual count/results.
- Prefer small cohesive commits, new branch + PR where applicable, explicit output paths and no secrets/data checked in.
- Update README status to distinguish tested historical B+C algorithms from actual newly executed original-data case validation. Document `cartopy` as an optional plotting dependency, not a universal numerical dependency.
- Provide researcher a short audit: changes, commands, observed metrics, test logs, blocked inputs, scientific decisions requiring approval.
- Do **not** create a `SKILL.md` claiming scientific automation is complete before these tests; optional skill can be a later deliverable.

## Non-goals

- No new 1999–2021 GIM download requirement; no 23-year reconstruction campaign.
- No relabeling, smoothing, inventing, or silently replacing original historical TEC.
- No change of quartile threshold k=3, z critical 1.96, 15-day reference, 30-day event observation, or k-means n_clusters=2 unless the researcher explicitly approves a documented experiment.
- No autonomous earthquake-causality determination.
- No changing Modern grids to legacy latitude ordering to fix presentation bugs.
