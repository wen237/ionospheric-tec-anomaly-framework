# Epicentral Zone Diagnostic: Scientific Feasibility & Minimum Scope Review

Date: 2026-11-17 (Asia/Taipei). Repository checkpoint inspected:
`0189f575fc7596fa0e11d3c20979a9d02633dc76`, branch
`agent/day5-controlled-host`. Git was clean before this review.

**Verdict: CONDITIONAL GO for a separate, offline, read-only diagnostic using
the saved A/B arrays.** The numerical inputs are sufficient. Acceptance of the
spatial reference and subsequent implementation require separate researcher
approval. This review implements no functionality and authorizes no execution.

## 1. Scientific purpose

Quantify the spatial relationship between the saved Framework D anomaly
occurrence distributions and an explicitly defined epicentral reference region.
Produce reproducible descriptive evidence: distances, grid-center membership,
regional counts and proportions, and differences between the two saved windows.

Membership is a geometric statement. Neither membership, proximity of a global
maximum, nor a high occurrence proportion establishes earthquake-ionosphere
causality, statistical significance, predictive skill, or precursor identity.
The diagnostic must not select windows, tune a radius to observed peaks, or
change an existing scientific selection or detector.

## 2. Relationship to the published SAVF methodology

The researcher's supplied paper context places historical anchors and polarities
before the establishment of temporal windows and global temporal anomaly
detection. The proposed diagnostic follows the saved spatial calculation. It
adds quantitative spatial descriptions without changing those earlier steps.
An anchor remains distinct from a complete UTC window.

The supplied Figure (c) context is the negative occurrence distribution for
2022-05-28 through 2022-06-01 UTC, with a maximum of 85%. Figure (d) displays an
epicenter, circular reference region and maximum negative grid. The saved
Experiment A independently reproduces the stated window and global maximum.
This review does not modify or reinterpret either published figure. No full
published SAVF paper or frozen Figure (d) rendering invocation was provided for
independent figure-by-figure verification.

Inspection resolved the circular-region implementation in the available code:

- `validation/legacy/spatial_verification/old_spatial_verification.py`:
  `SpatialSearch.__init__` sets `pd_radii = 10 ** (0.43 * magnitude)`;
  `ShowSpatialResults.plot_fig` draws a Matplotlib `Circle` with radius
  `pd_radii / 111` in longitude/latitude coordinates.
- `src/spatial_verification/spatial_plot.py` preserves the same formula and
  degree-circle approximation, explicitly documenting that it is not geodesic.
- `validation/spatial_verification/reproduce_afghanistan_spatial.py` fixes
  magnitude 6.0 and location `(33.020, 69.464)`. The validation README records
  the same coordinates and the 120-hour reference window.

Thus the available plotting lineage already uses the proposed magnitude-radius
relation. A spherical-distance region is a separately specified quantitative
reference: `R/111` applied equally to latitude and longitude is not its exact
boundary, especially away from the equator. Leave the historical drawing intact
and label this distinction in future results. Both definitions happen to select
the same three centers in this case; their continuous boundaries still differ.

## 3. Existing reusable code and data

Paths below are relative to the repository root.

| Existing component | Reuse and limit |
| --- | --- |
| `src/spatial_verification/spatial_anomaly.py` | `SpatialAnomalyResult` describes counts, percent ratios, axes and duration. Source inspection confirms full-window denominators. Do not call the detector. |
| `src/spatial_verification/spatial_grid.py` | Canonical axes: 71 ascending latitudes from -87.5 to 87.5, 73 longitudes from -180 to 180; 2.5-degree latitude and 5-degree longitude spacing. `orient_gim_grid` is a Legacy flip, not a Modern operation. |
| `src/workflow/modern_spatial_input_adapter.py` | Existing Modern D entry point and canonical orientation contract; inspect only, no new input preparation or execution. |
| `src/workflow/spatial_summary_export.py` | `_maximum_anomaly(..., grid_orientation="canonical")` returns global maxima and tied centers, and no points for an all-zero map. Reuse its established selection behavior. |
| `src/workflow/spatial_summary.py` | `SpatialSummary.preparation_radius_km` already evaluates `10.0 ** (0.43 * magnitude)` and validates serialized radius consistency. No new radius model is needed. |
| `src/spatial_verification/spatial_plot.py` | Existing cell-center convention, nominal cell edges, peak markers, degree circle, optional coastlines/borders. Plotting provides no regional quantitative verification. |
| `examples/compare_afghanistan_mvp_spatial.py` | `_arrays`, `_differences`, `_reference_checks` and saved schemas provide canonical-grid validation, count/ratio checks, signed B-minus-A arithmetic and A's reference checks. Do not invoke `plan`, `run`, `_input_validity`, or `_run_modern_d`. |
| `src/agent/scientific_evidence_tools.py` | `EvidenceTools(..., "post_spatial")` validates existing evidence snapshots entirely offline. Existing views expose global peaks, whole-grid comparisons, or one nearest grid center; none computes EPZ summaries. |
| `src/workflow/earthquake_catalog_adapter.py` | Historical catalog adapter, not the authoritative metadata source for this confirmed 2022 event. |
| `outputs/afghanistan_mvp02b_comparison/` | Both `spatial_arrays.npz`, experiment summaries, copied selections, status files, comparison summary/report/plan and `cellwise_differences.npz` are accessible. No raw GIM or historical TEC is needed for this diagnostic. |

Searches of `src/`, `examples/`, `tests/` and `validation/` found existing radius
metadata and plotted circles, but no reusable great-circle/EPZ distance field,
regional EPZ mask, or partial-cell overlap calculation. The evidence interface's
nearest-center lookup uses absolute latitude and circular longitude differences;
it is not a great-circle-distance function or regional mask.

Each experiment NPZ contains exactly these ten fields:

| Fields | Shape and meaning |
| --- | --- |
| `positive_counts`, `negative_counts` | `(71, 73)`, float64 storage with finite, nonnegative integer-valued occurrence counts |
| `positive_ratio`, `negative_ratio` | `(71, 73)`, float64 percentages, exactly `counts / ratio_denominator * 100` |
| `latitudes`, `longitudes` | `(71,)`, `(73,)`, float64 canonical coordinates |
| `window_steps`, `ratio_denominator` | Scalar int64, 120 for A and 144 for B |
| `target_input_finite_counts`, `initial_reference_input_finite_counts` | `(71, 73)`, int64 input-availability diagnostics; not detector-valid counts |

Tests inspected include `tests/spatial_verification/test_spatial_grid.py`,
`tests/spatial_verification/test_spatial_plot.py`,
`tests/workflow/test_spatial_summary.py`,
`tests/workflow/test_spatial_summary_export.py`,
`tests/workflow/test_compare_afghanistan_mvp_spatial.py`,
`tests/test_modern_spatial_input_adapter.py`, and
`tests/agent/test_scientific_review_agent.py`. Existing coverage establishes useful
contracts for orientation, radius metadata, ties, zero maps, immutable arrays,
denominators, saved evidence integrity and comparison arithmetic. It does not
substitute for new distance/membership tests. These tests were read, not run.

## 4. EPZ definition and scientific limitations

Dobrovolsky, Zubkov and Miachkin (1979), *Estimation of the size of earthquake
preparation zones*, **117**, 1025-1044, describe a magnitude-dependent surface
strain reference radius:

`R_km = 10 ** (0.43 * M)`.

The publisher's abstract relates the radius to ground deformation and an
idealized elastic-inclusion model. It supports the equation and citation; the
subscription full text was not reviewed. A calibration range, magnitude-scale
conversion and numerical uncertainty were not established in this review.
[Primary source: Springer, DOI 10.1007/BF00876083](https://link.springer.com/article/10.1007/BF00876083).

**Scientific assessment:** the relation is suitable as a proposed, explicit,
literature-motivated retrospective spatial reference, subject to researcher
acceptance. This is an assessment of scope, not validation of a TEC preparation
zone. Use the saved M6.0 unchanged; do not substitute a different reported
magnitude or optimize the radius against either experiment.

For this feasibility calculation only, the proposed geographic convention is a
sphere with `earth_radius_km = 6371.0088`. This is an explicit numerical convention
to approve and record, not a detector threshold or an accepted physical boundary.
For latitude `phi` and longitude `lambda` in radians, relative to the confirmed
epicenter:

```text
delta_lambda = wrapped longitude difference in [-pi, pi)
h = sin((phi-phi0)/2)^2 + cos(phi0)*cos(phi)*sin(delta_lambda/2)^2
h = clip(h, 0, 1)                         # floating-point protection
d_km = 2 * earth_radius_km * atan2(sqrt(h), sqrt(1-h))
center_inside = (d_km <= R_km)             # inclusive; no radius inflation
signed_boundary_margin_km = d_km - R_km    # negative inside
```

Keep five concepts distinct:

1. The ground-based magnitude-radius relation supplies a reference distance.
2. TEC occurrence ratios describe a gridded ionospheric observable over an
   explicitly selected time window, not ground strain or TEC amplitude.
3. Grid-center membership tests a coordinate against that reference distance.
4. Partial-cell overlap concerns a nominal cell footprint, requiring a separate
   geometric definition; it is not determined by center membership.
5. Physical earthquake-ionosphere causality requires independent evidence and
   controls that this geometric diagnostic does not provide.

No altitude correction, magnetic-conjugate region, anisotropic boundary,
significance cutoff or new anomaly threshold is justified by these saved arrays.
The saved event does not record a magnitude type or uncertainty; do not invent
either or infer applicability to all magnitude scales. Retrospective selection,
coarse spatial sampling, spatially correlated grids and absent external controls
limit interpretation. Equal weighting of centers is not area weighting.

## 5. Independent numerical feasibility findings

### Identity, windows and integrity

The existing offline validator returned both `temporal_historical` and `spatial`
as `validated_snapshot`, with **23 fixed-file snapshots**. It checked hashes and
sizes, parent bindings, selection copies, event consistency, canonical arrays,
count/ratio arithmetic, saved peaks, all six A reference checks and complete
cell-wise differences. Its before/after rechecks passed. These are contract and
snapshot checks, not re-execution or independent validation of the detector.

The confirmed event in both experiment summaries, both saved selections and
the parent review bundle agrees:

| Field | Saved authoritative value |
| --- | --- |
| Event ID | `us7000hj3u` |
| UTC origin time | `2022-06-21T20:54:34Z` |
| Magnitude | 6.0 |
| Epicenter | 33.020 N, 69.464 E |
| Depth | 4.0 km; not an input to the radius or surface distance |

The [USGS event's region-information page](https://earthquake.usgs.gov/earthquakes/eventpage/us7000hj3u/region-info)
independently corroborates those values. Saved metadata remains authoritative
for this reproduction. The JavaScript executive page did not expose metadata
through the browser, and an attempted FDSN GeoJSON browser read failed; the USGS
indexed region-information page supplied the corroboration instead. No catalog
or scientific input was downloaded or replaced.

Do not use historical TEC filename coordinates `(33.092, 69.514)`, the MVP-01
scientific input coordinates `(33.02, 69.46)`, or the nearest Modern TEC sample
center `(32.5, 70)` as the confirmed event epicenter.

| Saved experiment | Selection basis | Inclusive UTC start | Inclusive UTC end | Hours and ratio denominator |
| --- | --- | --- | --- | --- |
| A | Independent published reference | 2022-05-28 00:00 | 2022-06-01 23:00 | 120 |
| B | Saved Cluster 1 deterministic candidate | 2022-05-28 00:00 | 2022-06-02 23:00 | 144 |

Both saved parameter sets are `reference_days=15`, `k=3.0`,
`grid_orientation="canonical"`, `show_boundaries=false`. Selection records were
read, not regenerated or treated as authenticated execution authorization.

### Radius, center mask and peaks

At saved magnitude 6.0, `R = 380.1893963205613 km`. A single spherical-distance
mask on the common canonical grid contains **3 centers**, used unchanged for A
and B. Coordinates and indices below are in canonical order, with zero-based
indices. All positive counts and positive ratios at these three centers are zero
in both experiments.

| Row, column | Center (latitude, longitude) | Distance (km) | A negative count / percent | B negative count / percent | B-minus-A count / percentage points |
| --- | --- | --- | --- | --- | --- |
| 47, 50 | 30.0, 70.0 | 339.629803 | 102 / 85.000000 | 103 / 71.527778 | +1 / -13.472222 |
| 48, 50 | 32.5, 70.0 | 76.520368 | 95 / 79.166667 | 96 / 66.666667 | +1 / -12.500000 |
| 49, 50 | 35.0, 70.0 | 225.640164 | 85 / 70.833333 | 86 / 59.722222 | +1 / -11.111111 |

| Global peak center | Polarity | A count / percent | B count / percent | Distance (km) | Center in proposed EPZ? |
| --- | --- | --- | --- | --- | --- |
| 30.0, 70.0 | Negative | 102 / 85.000000 | 103 / 71.527778 | 339.629803 | Yes |
| -22.5, -155.0 | Positive, tied | 12 / 10.000000 | 12 / 8.333333 | 15521.477157 | No |
| -22.5, -150.0 | Positive, tied | 12 / 10.000000 | 12 / 8.333333 | 15985.844342 | No |

Every global peak and tie agrees with the saved summaries. Spherical distance
was also independently evaluated using `atan2(norm(cross(u,v)), dot(u,v))` on
unit vectors over all 5,183 centers. The largest absolute discrepancy from the
haversine calculation was `1.0913936421275139e-10 km`; the numerical assertion
used `atol=1e-8 km, rtol=0` solely for this arithmetic cross-check. This tolerance
does not enlarge the membership boundary. Repeated mask arithmetic was identical.

Mask fingerprint: SHA-256 of the `(71,73)` mask converted to `uint8`, serialized
in C row-major order (5,183 bytes):

`7644ce22be563963c99ed349737aa4a7ac582a5d4d2495f0fa49512ba89063c3`.

### Regional summaries and A/B comparison

For polarity `s`, let `C_X,s(g)` be the saved count and `P_X,s(g)` its saved
percentage at included center `g`. Proposed minimum aggregates are:

```text
N = number of included centers
regional_count_sum_X,s = sum_g C_X,s(g)
regional_mean_ratio_percent_X,s = mean_g P_X,s(g)
                              = 100 * regional_count_sum_X,s / (N * H_X)
regional_count_delta_s = sum_g (C_B,s(g) - C_A,s(g))
regional_mean_ratio_delta_pp_s = mean_g (P_B,s(g) - P_A,s(g))
```

Here `H_A=120`, `H_B=144`, `N=3`. Each per-center ratio retains its original
denominator. `N*H` appears only when explaining the aggregate grid-hour mean;
it does not replace a saved denominator. It is not a detector-valid denominator.

| Regional quantity | A | B | B minus A |
| --- | --- | --- | --- |
| Included centers | 3 | 3 | 0 |
| Positive count sum, grid-hour occurrences | 0 | 0 | 0 |
| Positive mean ratio, percent | 0 | 0 | 0 percentage points |
| Negative count sum, grid-hour occurrences | 282 | 285 | +3 |
| Negative mean ratio, percent | 78.33333333333333 | 65.97222222222223 | -12.361111111111112 percentage points, from mean of cell differences |
| Negative per-center count range | 85-102 | 86-103 | Each cell increases by 1 |
| Negative per-center ratio range, percent | 70.833333-85.000000 | 59.722222-71.527778 | Cell differences range -13.472222 to -11.111111 percentage points |
| Aggregate grid-hour denominator, for mean interpretation only | 360 | 432 | +72 |

The regional sums and cell-wise signed differences were recomputed in memory;
the latter match the corresponding saved difference-array slices exactly.
Reduction order can cause last-bit differences between subtracting rounded or
separately reduced means and taking the mean of cell differences. Specify the
latter convention for the output and do not treat this as a scientific mismatch.

282 is not 282 distinct UTC hours: one hour may contribute at several centers.
The mean is an unweighted mean over three sampled centers, not the fraction of
EPZ area anomalous, probability of an earthquake, or probability that any point
in the EPZ is anomalous. Increasing counts alongside decreasing ratios is
consistent with the 24-hour extension and larger original denominator. It does
not establish stronger or weaker seismic association.

### Resolution, boundary and validity limits

Nominal spacing near this epicenter is approximately 277.988 km north-south and
466.174 km east-west under the proposed sphere. Only three included centers is
therefore a substantial sampling limitation, not a resolved regional footprint.

- Closest included center to the boundary: `(30,70)`, signed margin
  `-40.559594 km`. The nominal cell's south-edge midpoint `(28.75,70)` is
  `477.547487 km` from the epicenter, outside the radius although its center is
  inside.
- Closest excluded center: `(32.5,65)`, distance `421.375593 km`, signed margin
  `+41.186196 km`. Its nominal east-edge midpoint `(32.5,67.5)` is only
  `192.534930 km` away, inside the radius although its center is outside.

These examples demonstrate boundary crossing under the plotting convention's
rectangular nominal cells. They do not compute cell-intersection areas or assume
a uniform TEC signal within a cell. Report signed margins without inventing a
"near-boundary" cutoff or using overlap to alter the center mask.

The canonical longitude array includes both -180 and +180, the same physical
meridian. Neither endpoint column is in this Afghanistan mask. Preserve all
5,183 stored entries and original global maxima. A future general-purpose region
crossing the dateline needs an explicit seam deduplication/weighting policy for
regional aggregation; it must not silently count duplicate physical centers.
Wrapped distances alone do not settle that policy.

Saved input availability is incomplete globally:

| Availability diagnostic | A global minimum-maximum | B global minimum-maximum | Within the three-center mask |
| --- | --- | --- | --- |
| Target finite-input counts | 92-120 | 103-144 | A: 120 at each; B: 144 at each |
| Initial reference finite-input counts | 277-360 | 277-360 | 360 at each in both |

All saved count/ratio cells are finite, but `np.nansum` in the detector can return
zero even when classifications were unavailable. A zero count alone does not
prove a valid, normal observation. Neither availability array exposes per-hour
reference validity or effective detector-valid sample counts. The initial
360-hour reference counts also do not directly describe every later rolling
reference. Keep `effective_detector_valid_counts=null`; do not infer it from
finite-input totals, change the denominators, or claim complete detector validity
even at centers with full finite-input availability.

| Requested calculation | Feasible from saved evidence? |
| --- | --- |
| A. Magnitude-radius evaluation | Yes, after approval of this reference |
| B. Distance to each canonical center | Yes, under an explicit spherical convention |
| C. Distance to every tied global peak | Yes |
| D. Peak-center membership | Yes; distinct from full-cell coverage |
| E. Both polarities' regional summaries | Yes, with center/grid-hour semantics |
| F. Comparable A/B regional results | Yes; identical grid, event and shared mask |
| G. Regional B-minus-A counts and ratios | Yes; ratios in percentage points, original denominators |
| H. Included-center count | Yes, 3 for this proposed definition |

Saved aggregate arrays cannot recover hourly spatial co-occurrence, duration or
ordering, valid-detection-adjusted rates, within-cell TEC distributions, or
area-resolved anomaly coverage. Geometric overlap could later be approximated
under an explicitly chosen cell model, but is not an observed anomaly footprint.
No Kp, Dst or F10.7 controls are available through the inspected evidence views;
spatial significance and physical attribution remain unanswered.

## 6. Minimum proposed implementation

**Required after approval:** one case-specific read-only example, provisionally
`examples/diagnose_afghanistan_epicentral_zone.py`, plus its focused synthetic
test file. Neither is created in this review. A new framework, Stage 2 pathway,
detector run, plotting dependency or model tool is unnecessary.

The smallest reuse path is the existing offline `EvidenceTools` snapshot loader,
followed by pure NumPy spherical geometry and masked reductions. Despite its
location under `src/agent/`, the inspected loader imports no OpenAI client and
makes no LLM/API calls. Use its validated snapshots directly; do not create an
Agent, dispatch model tool calls, register tools or change orchestration. This
path retains the existing MVP-01 parent-bundle and selection bindings, which are
present here. It must fail explicitly if they are missing or invalid, rather
than synthesizing evidence or executing frameworks to repair it.

Reuse the canonical constants and established global-maximum helper; retain
`grid_orientation="canonical"`. The scalar radius is direct evaluation of the
already established relation, with the existing radius-property test as a
compatibility reference. Do not construct fake workflow/Stage 2 objects merely
to access that property, duplicate a detector or write a new peak extractor.
One small pure distance/mask calculation is needed because none exists locally.
No refactoring of Framework D or the current plotting code is required.

The example should accept a host-supplied evidence root and a fresh output JSON
path outside the evidence directories. Its scientific configuration identifies
the approved radius relation, fixed saved event magnitude, sphere radius and
inclusive grid-center rule. It produces one new local JSON report, with
source hash checks before and after calculation and no overwrite. It writes no
scientific arrays, maps or copies of inputs.

**Optional later extensions:** a shared scalar radius helper; a general-purpose
diagnostic module; ellipsoidal-distance sensitivity; explicitly defined nominal
cell overlap; area-weighted summaries; a new geodesic overlay in a separately
named figure; controls and other events; a bounded read-only Agent evidence view
after scientific acceptance. None is required for the initial center diagnostic.
Generalizing to dateline-crossing regions requires the separate seam policy
described above. Keep all such extensions out of the first case-specific change.

## 7. Data and provenance contract

Proposed output schema, version 1; this table specifies future fields, not a new
artifact generated now:

| Field/group | Required content |
| --- | --- |
| `record_type`, `schema_version` | Dedicated EPZ diagnostic identity and integer version; do not reuse a Stage 2 or Agent assessment schema |
| `event` | Saved event ID, origin UTC, latitude, longitude, magnitude, depth and source reference; explicit source artifact binding; magnitude type/uncertainty unavailable |
| `epz_reference` | Relation ID, DOI, exponent 0.43, radius in km, magnitude source, spherical-distance method, Earth radius in km, `grid_center` membership, inclusive boundary, `partial_cell_overlap_computed=false` |
| `grid` | `(71,73)`, canonical orientation, axis identities/hashes, spacing, stored endpoint-meridian duplication and its non-inclusion in this case |
| `mask` | Included count, all row/column indices and coordinates in row-major order, center distances, signed margins, mask SHA-256 and exact byte convention; closest inside/outside margins |
| `experiments.A`, `experiments.B` | Saved experiment/selection identities, inclusive UTC bounds, hours, original denominator, unchanged detector parameters; every tied global peak with count, percent, distance and center-membership flag |
| `experiments.*.regional` | Both polarities: per-center saved counts and percentages, count sum, mean ratio, minima/maxima, included-center count and nominal `N*H` interpretation; units on every aggregate |
| `differences_b_minus_a` | Each included center's signed count/percentage-point differences; regional count-sum and mean-cell-ratio differences; explicit direction and 120/144 denominators |
| `validity` | Target/initial-reference finite counts or summaries clearly labeled as availability; `effective_detector_valid_counts=null`; zero-count and rolling-reference caveats |
| `provenance` | Relative artifact identities, SHA-256 and sizes of loaded sources and parent bindings; recorded original source/code hashes distinguished from current diagnostic source hash, Git revision and Python/NumPy versions; before/after recheck result |
| `limitations`, `review_state` | Descriptive-only purpose; center-versus-area distinction; absent controls; researcher approval status; execution eligibility remains false; no causal or automated precursor verdict |

Required input validation: exact supported record types/versions and field sets;
saved event/selection consistency; hourly UTC bounds matching duration; canonical
axes identical across A/B; expected shapes and numeric dtypes; finite ratios in
0-100; integral counts in 0-H; exact saved count/ratio equality; original scalar
denominators; saved delta consistency; no object-array pickle loading. Reuse
existing bounded NPZ/JSON readers and path checks. Validate the proposed sphere
radius and all event values as finite with valid units and coordinate ranges.
Do not accept an arbitrary radius override selected by inspecting the peaks.

Determinism requires fixed input bytes and approved parameters; row-major cell
ordering; existing global-peak tie behavior; fixed NumPy reduction order; JSON
with sorted keys, fixed formatting/newline, full numeric precision and no NaN or
Infinity. Do not embed output paths, wall-clock timestamps or random run IDs in
the scientific payload. Pin code/environment for byte-identical runs; cross-
environment floating-point tolerance is a numerical test concern, never an
expanded scientific boundary. Do not claim deterministic NPZ bytes from new ZIP
serialization; no NPZ output is needed.

For an empty mask, report zero centers and zero summed occurrences, with null
means/ranges and an explicit empty-mask status. Never divide by zero or select a
nearest cell to replace an empty mask. For an all-zero anomaly map, preserve the
established global helper's empty peak list and the detector-validity caveat.

Hashes establish snapshot consistency, not source authenticity, OS custody or
human authorization. This review checked saved source declarations and bindings,
not the external raw TEC/GIM/catalog files or historical detector correctness.
Absolute host paths inside saved records are not prerequisites or credentials
and should not be copied into the new portable report. Keep generated scientific
reports and data local under ignored output paths; do not commit research arrays
or images.

## 8. Acceptance tests required before scientific acceptance

These are **proposed tests, not executed test results**. Use synthetic arrays
and fixed numerical geometry, with no raw-data retrieval or framework execution.

| Required test | Expected evidence |
| --- | --- |
| Radius definition | M6.0 evaluates to 380.1893963205613 km within numerical tolerance; agrees with the existing relation; finite/invalid inputs handled |
| Analytic spherical distances | Coincident points give zero; equatorial quarter-circle gives `pi*earth_radius/2`; antipodes give `pi*earth_radius`; symmetry and independent unit-vector checks |
| Longitude wrapping | 179 to -179 uses a 2-degree separation; -180/+180 aliases agree; polar and near-antipodal cases stay finite; no unapproved coordinate coercion |
| Membership boundary | Points strictly inside/outside classified correctly; exact stored distance equal to radius included; no `isclose`-based radius inflation |
| Canonical orientation | Asymmetric synthetic north/south values map to correct coordinates; canonical Modern data never flipped; mismatched/Legacy axes rejected in this case-specific entry |
| Shared mask | Both experiments use identical event, axes, mask bytes and indices; disagreements fail before output |
| Center versus cell | A center-inside/cell-straddling example and a center-outside/cell-overlapping example remain distinct; no area-coverage field presented as measured |
| Global maxima | All established tied maxima retained; all-zero map has no marked peaks; distance lookup uses the actual canonical indices |
| Count/ratio semantics | Synthetic 120/144 examples preserve both denominators, including unchanged or increased counts with decreased ratios; do not divide by finite-input or effective-valid estimates |
| Signed differences | Signed B-minus-A count arithmetic cannot underflow; percent differences use percentage points; cell/reduced results match saved differences |
| Aggregation | Hand-calculated sums, unweighted means and ranges agree; empty mask uses null means/ranges; zero region keeps the validity caveat |
| Missingness | Reduced finite availability does not masquerade as detector validity; missing effective counts remain null; missing/nonfinite/out-of-contract arrays fail without repair |
| Integrity and immutability | Changed NPZ/metadata/selection or parent binding is rejected; all source bytes/hashes unchanged; no source-array mutation or existing-output overwrite |
| Reproducibility | Repeated fixed-input reports byte-identical under the pinned environment; mask fingerprint and ordering stable |
| Offline boundary | Block any framework runner, network/SDK call and Agent orchestration in the test harness; diagnostic remains usable without an OpenAI package/key |
| Scientific claims | Output states descriptive scope and missing controls; no automated causality, significance, precursor classification or changes to saved selection rules |

A dateline-crossing aggregation test is mandatory if the implementation expands
beyond this Afghanistan case; the physical duplicate-meridian policy must first
be approved. Distance-wrap tests are required even for this initial case.

After separate implementation approval, a researcher-reviewed read-only check
against these saved arrays should reproduce the values and mask fingerprint in
Section 5. That future acceptance run is distinct from the present feasibility
arithmetic and must preserve the baseline hashes below.

## 9. Outstanding scientific decisions

Required before implementation/scientific acceptance:

1. Accept the Dobrovolsky relation as a named retrospective spatial reference
   using saved M6.0, with no claim that this validates a physical TEC EPZ.
2. Accept the proposed spherical constant `6371.0088 km`, wrapped great-circle
   distances and inclusive center-membership convention, explicitly distinct
   from the historical degree-circle drawing.
3. Accept count sums as grid-hour occurrences and the regional mean as an
   unweighted mean of included center percentages with unchanged denominators.
4. Accept signed boundary margins and explicit coarse-grid/missing-validity
   limitations for the initial scope. No overlap threshold or overlap weighting
   is proposed. Decide separately if nominal geometric overlap is later needed.
5. Provide separate implementation approval. Technical feasibility and this
   document do not establish trusted authorization or Windows isolation.

Unanswered by the saved aggregates: within-hour spatial coincidence, valid-only
rates, true areal TEC coverage, association significance relative to an approved
null/control design, physical mechanisms and precursor identity. Magnitude-scale
calibration and reference-radius uncertainty need additional scientific review
if quantitative physical interpretation is contemplated. Exact published-panel
rendering provenance requires the original figure invocation/materials; its
absence does not block this separately labeled descriptive diagnostic.

## 10. Verdict and review stop

**CONDITIONAL GO.** The existing validated saved A/B arrays support every requested
center-based calculation A-H. The smallest useful next change is one offline
case-specific example with focused synthetic tests and one deterministic JSON
output. No new download, dependency, scientific threshold, detector execution,
model tool or Framework D modification is needed.

Implementation remains pending separate researcher approval of scope and the
reference conventions. Full-cell coverage and earthquake-ionosphere causality
claims are outside the supported minimum scope. No scientific selection or
published-paper result has been changed.

Stop point: **Scientific & Security Review**.

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```

## Audit: executed checks and preserved artifacts

Only `docs/day5_epicentral_zone_diagnostic_scope.md` was created. No implementation,
pytest run, Framework A/B/C/D run, protected execution, OpenAI/other LLM call, dependency
installation, commit, push, tag or PR was performed. Literature and USGS pages
were read through the browser; no scientific input dataset was fetched.

Git's initial ordinary status/branch reads failed with dubious ownership. These
read-only retries succeeded using a per-command setting, with no global config
change:

```powershell
git -c safe.directory=C:/Users/Wen/Documents/GitHub/ionospheric-tec-anomaly-framework status --short
git -c safe.directory=C:/Users/Wen/Documents/GitHub/ionospheric-tec-anomaly-framework branch --show-current
git -c safe.directory=C:/Users/Wen/Documents/GitHub/ionospheric-tec-anomaly-framework rev-parse HEAD
```

Source searches used `rg --files` and `rg -n` over the paths listed in Section 3.
Evidence hashes were read with `Get-FileHash -Algorithm SHA256`, before and after
the review. Local numerical commands used the existing
`.venv/Scripts/python.exe -B -`, with PowerShell here-strings on stdin; no Python
script was saved. Environment observed: Python 3.10.6, NumPy 2.2.6.

The following exact compact audit command was executed in addition to the
larger in-memory assertion check described in Section 5. It reproduces the core
feasibility values without running a framework or creating output:

```powershell
@'
import hashlib, numpy as np
from src.agent.scientific_evidence_tools import EvidenceTools
e = EvidenceTools('outputs', 'post_spatial')
assert e.status == dict(temporal_historical='validated_snapshot', spatial='validated_snapshot')
a, b = e.arrays['A'], e.arrays['B']
v = e.summaries['A']['event']
lat, lon = np.meshgrid(a['latitudes'], a['longitudes'], indexing='ij')
p0, p = np.deg2rad(v['latitude']), np.deg2rad(lat)
dl = np.deg2rad((lon - v['longitude'] + 180.0) % 360.0 - 180.0)
h = np.clip(np.sin((p-p0)/2)**2 + np.cos(p0)*np.cos(p)*np.sin(dl/2)**2, 0, 1)
d = 2 * 6371.0088 * np.arctan2(np.sqrt(h), np.sqrt(1-h))
r = 10.0 ** (0.43 * v['magnitude'])
m = d <= r
print('radius_km, centers, mask_sha256:', r, m.sum(), hashlib.sha256(m.astype('uint8').tobytes()).hexdigest())
for label, z in [('A', a), ('B', b)]:
 print(label, 'hours:', int(z['ratio_denominator']), 'negative count sum / mean percent:', z['negative_counts'][m].sum(), z['negative_ratio'][m].mean())
print('centers and distances:', [(float(lat[i,j]), float(lon[i,j]), float(d[i,j])) for i,j in np.argwhere(m)])
e.recheck()
print('saved-snapshot recheck: PASS')
'@ | & '.venv/Scripts/python.exe' -B -
```

Observed exit code 0. Results: radius `380.1893963205613`, 3 centers, the mask hash
recorded above; A `120, 282.0, 78.33333333333333`; B
`144, 285.0, 65.97222222222223`; saved-snapshot recheck PASS. The larger audit
also set source arrays read-only in memory, asserted event/grid consistency,
cross-checked all distances by unit-vector geometry, matched regional differences
to saved arrays, and repeated the mask calculation. Its assertions all passed.
The separate nominal-cell-edge arithmetic also exited 0 with the distances in
Section 5. No pytest tests were run; a full suite is explicitly outside this
review's authorized scope.

All **16 files** in the comparison directory were separately inventoried and
hashed. The baseline below was rechecked after the report was written: identical
file set, sizes and SHA-256 values. Paths are relative to
`outputs/afghanistan_mvp02b_comparison/`; `A/` abbreviates
`experiment_a_reference_120h/`, `B/` abbreviates `experiment_b_candidate_144h/`.

| Artifact | Bytes | Preserved SHA-256 |
| --- | --- | --- |
| `cellwise_differences.npz` | 16697 | `ad31c93794d363e31acbdfbd6dd33724f99f0b9fd14c4ae32e2d402108728ec4` |
| `comparison_plan.json` | 30858 | `7af0940c0e96c01c20850f8e414351e58abb30a7e41ffea6221ef87117a946a5` |
| `comparison_report.md` | 2082 | `ac3a6ebd2b19717ef7b7df331ad84c9e0da514defdfdb3eb0b49edab9413fc71` |
| `comparison_summary.json` | 43809 | `588a7f44b11ea678a5ab98df2ce787a43f38f08100f309a7dd5c56e8e4b5562b` |
| `A/execution_status.json` | 167 | `53de483a2956b8d6faa29cbf1a1ada071d54dcaf95decfdaddd5aae8a7e3935e` |
| `A/experiment_summary.json` | 18805 | `d10636b594b5070d191b35fb1c1c98979a06f67bde8668ab60552cf968a1d573` |
| `A/negative.png` | 210773 | `a618a39994b027296271019f63aad39f1d596e778f7b8a24b7eb63b17c7b9289` |
| `A/positive.png` | 141181 | `a466dc7e7723e5b4011c8b52c30a526e6a8ea2d7a7cc8a804164bbaa1134c063` |
| `A/selection_record.json` | 16934 | `ddc032ed73fc25aa8a82a233574a7fd28634f1fa58e7f3aa4b447be5d69bc464` |
| `A/spatial_arrays.npz` | 20001 | `8a9a03419dcb4f8075af867354d51b4441ca3fb81a918bb1acea2521bacd681f` |
| `B/execution_status.json` | 167 | `53de483a2956b8d6faa29cbf1a1ada071d54dcaf95decfdaddd5aae8a7e3935e` |
| `B/experiment_summary.json` | 18732 | `3ec34e6d60b4f42599b37dde25e250c68e71287ad629270342ffa6052b3dde26` |
| `B/negative.png` | 209335 | `e264b1a33b08124250ab050d2cbb84060b7a50d046b1d35d3c49ea27b378728c` |
| `B/positive.png` | 143053 | `4b73068ce62409a168e8c328b5c8d8ad5f6f8e8872501d5500d2a7c6cea0249b` |
| `B/selection_record.json` | 24657 | `eb85bb59a6c0710decc0bdde344a66e5b2f641a1e852e1965ff1705e6eab86f7` |
| `B/spatial_arrays.npz` | 19922 | `c565594d3d30767ac10b156125e9ec5e0df2ae06e62c3225418b8b5aa5741b5c` |

Legacy differences are confined to the proposed spherical boundary versus its
degree-circle rendering, and the already saved A/B duration comparison. There is
no numerical alteration of Legacy, Modern D, A's 85%/10% reference, source grids,
polarity or UTC bounds. What remains pending is scientific adoption of the
reference, separate implementation approval and the future acceptance tests.
