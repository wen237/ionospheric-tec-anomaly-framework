# Agent guidance for ionospheric-tec-anomaly-framework

This repository implements independently validated TEC anomaly frameworks (A temporal, B statistical, C clustering, D spatial). The human researcher is the scientific authority.

## Start here

Read [docs/agent_handoff.md](docs/agent_handoff.md) before changing code. Confirm current Git status, inspect existing modules and tests, and give a short plan before acting. Prefer existing tested `src/` functions to new framework layers.

## Scientific non-negotiables

- Do **not** alter scientific algorithms, thresholds, source grids, polarity, UTC conventions, or existing fixed regression references solely to make a test pass.
- Keep historical 1999-01-01 to 2021-12-31 analysis distinct from the 2022 Afghanistan event. Framework A/D example uses 2022 data; historical B+C uses the earlier period.
- Use the **original saved historical TEC dataset** for the remaining Afghanistan B+C reproduction. **Do not download, reconstruct, replace, or require a newly downloaded 23-year global GIM dataset.** The previously developed modern historical reconstruction remains archival/optional, not a prerequisite.
- For historical earthquakes, use the verified USGS filtered CSV through `src/workflow/earthquake_catalog_adapter.py` when present; the old `eqlist.npy` is the comparison baseline. The reference has 741 daily representative events, of which 74 have M >= 6.0 and eligible analysis windows.
- Never infer a complete spatial-verification UTC window from a single K-means temporal anchor. Candidate windows must state how they were derived; obtain explicit researcher approval before scientific interpretation or default Stage 2 execution.
- Modern GIM gridded TEC latitude is ascending, and map / spatial-summary coordinates must agree. Do not apply a second legacy north-south flip on the modern path. Preserve the explicit legacy grid convention separately.
- Preserve existing 2022 D validation: 120 hourly samples, 71 x 73 = 5183 grids, positive maximum 10% at (-22.5,-155) and (-22.5,-150), negative maximum 85% at (30,70).
- Never commit research CSV, NPZ, NPY, local raw GIM, private paths as credentials, output images, or downloaded Cartopy caches. Keep them out of Git.

## Workflow

1. Read `docs/agent_handoff.md`, available inputs, and test suite.
2. Finish the still-incomplete legacy historical-TEC B+C end-to-end reproduction using existing adapters and the **original** files. Verify selected events and scientific outputs; explicitly identify any unresolved differences.
3. Establish a clear, testable Stage 2 Modern-GIM entry point, reusing the validated Modern D calculations and corrected visualizations, without replacing the Legacy Stage 2 pathway.
4. Add a **review-only** candidate-window report using Framework A daily anomaly hours and (once available) B+C anchors. The researcher makes the final selection. Do not silently equate an anchor with a window or claim scientific precursor identification.
5. Run focused tests followed by `python -m pytest tests -q`. Record executed tests, failures, and artifacts; do not claim any run that you did not actually perform.
6. Work in small, reviewable commits on a separate branch / PR where available. Avoid unrelated refactoring, unrequested dependency expansion, and overwriting validated outputs.

## Local-only dependencies

The original Afghanistan historical TEC and earthquake data were stored outside this repository. Do not assume their Windows drive paths exist inside an agent environment. Check whether files are accessible; otherwise request them as attached/mounted inputs and continue independently on code/tests. Never synthesize missing TEC or earthquakes.

## Handoff and acceptance

For each task, report exact changed paths, command lines, observed results, differences from Legacy, and what remains blocked. Final scientific approval and any decision to merge are reserved for the researcher.
