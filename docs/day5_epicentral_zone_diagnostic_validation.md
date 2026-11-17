# EPZ Diagnostic V1: Scientific Validation Record

Date: 2026-11-17 (Asia/Taipei).

## 1. Validation scope and verdict

**ACCEPTED for case-specific descriptive scientific analysis**, following the
researcher's review. The implementation and saved results are ready for a
researcher-controlled Git checkpoint within the boundaries below.

This documentation task inspected the accepted files, compared saved JSON bytes
and hashes, checked saved values, and rehashed referenced artifacts. It did not
rerun the diagnostic, tests or scientific frameworks. The earlier scope document
and saved JSON `researcher_review="pending"` state remain unchanged; subsequent
researcher acceptance is recorded here without rewriting those artifacts.

## 2. Exact implementation and test-file identities

Repository-relative identities, verified from file bytes:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `examples/diagnose_afghanistan_epicentral_zone.py` | 16604 | `52d2f406e0078e34e635f66c680a4b47112fef6cca0f7195427922030a94ee02` |
| `tests/workflow/test_diagnose_afghanistan_epicentral_zone.py` | 19057 | `8cf28eab6b3f62665e7943ca0b5bc9ef8deaaeeb5529bd4119e58eaeb1b68fb6` |
| `docs/day5_epicentral_zone_diagnostic_scope.md` | 38859 | `d2a9fd585a9e25a276ce775cb7b887f76616412aaa4eeeebc020646dfb227f8a` |

Output record type: `afghanistan_epicentral_zone_diagnostic`; schema version: 1.
All five accepted files, including both JSON reports, were preserved unchanged.

## 3. Scientific parameters

- Confirmed event: Afghanistan M6.0, `us7000hj3u`, origin
  `2022-06-21T20:54:34Z`, epicenter **33.020 N, 69.464 E**.
- Reference: `R_km = 10 ** (0.43 * M)`, DOI `10.1007/BF00876083`;
  saved radius **380.1893963205613 km**.
- Sphere radius: **6371.0088 km**; wrapped spherical haversine distances.
- Membership: `grid_center_distance_km <= epz_radius_km`, inclusive, with
  **zero radius tolerance**. One shared canonical mask serves both experiments.
- Canonical grid: 71 ascending latitudes by 73 longitudes, with 2.5-degree
  latitude and 5-degree longitude spacing. Modern arrays receive no Legacy flip.
- Saved Framework D parameters remain 15 reference days and `k=3.0`.
  Original 120-hour and 144-hour percentage denominators are preserved.

Three included centers, with zero-based canonical indices:

| Latitude N | Longitude E | Row | Column |
| ---: | ---: | ---: | ---: |
| 30.0 | 70.0 | 47 | 50 |
| 32.5 | 70.0 | 48 | 50 |
| 35.0 | 70.0 | 49 | 50 |

Saved mask SHA-256:
`7644ce22be563963c99ed349737aa4a7ac582a5d4d2495f0fa49512ba89063c3`.
Its recorded encoding is a `(71,73)` uint8 0/1 mask in C row-major order,
5,183 bytes. This task verified the fingerprint recorded in the accepted output;
it did not recalculate the scientific mask.

## 4. Real A/B diagnostic results

Values below were read directly from the saved JSON, then compared with the
researcher's verification targets; targets were not substituted for evidence.

| Experiment | Inclusive UTC window | Hours / original denominator | Negative grid-hour occurrence sum | Unweighted mean negative ratio (%) |
| --- | --- | ---: | ---: | ---: |
| A | 2022-05-28 00:00 through 2022-06-01 23:00 | 120 | 282 | 78.33333333333333 |
| B | 2022-05-28 00:00 through 2022-06-02 23:00 | 144 | 285 | 65.97222222222223 |

Saved B-minus-A negative results: **+3 grid-hour occurrences** and
**-12.361111111111112 percentage points**, the mean of the cell-wise percentage
differences. Both experiments have zero positive regional counts and zero
unweighted positive regional mean percentages. Greater negative counts with a
lower mean percentage reflect the different original duration denominators;
they do not establish a change in earthquake association.

## 5. Reproducibility and output hashes

| Accepted local output | Bytes |
| --- | ---: |
| `outputs/afghanistan_epz_diagnostic_run01/diagnostic.json` | 23441 |
| `outputs/afghanistan_epz_diagnostic_run02/diagnostic.json` | 23441 |

Both independently hashed files have SHA-256:
`d0e7d0e2127ba66599b9dd0a808be1b1cc0add5ecae2902fae09bcbbc952c1b4`.
This matches the researcher-verified fingerprint. The two real diagnostic runs
were previously reported byte-identical; this task independently reconfirmed
equal sizes, equal hashes and exact byte equality without regenerating either.
Recorded environment: Python 3.10.6, NumPy 2.2.6.

## 6. Prior implementation validation and provenance limits

**Previously executed focused test, not a new test run:**

```powershell
& '.venv/Scripts/python.exe' -B -m pytest tests/workflow/test_diagnose_afghanistan_epicentral_zone.py -q -p no:cacheprovider
```

Observed prior result: **43 passed in 244.70s (0:04:04)**. The hand-authored
synthetic tests cover geometry, exact boundaries, canonical/shared masks, empty
regions, ties, count/ratio semantics, signed differences, deterministic output,
source failures, no overwrite, immutability and prohibited execution sentinels.
That execution record comes from the preceding implementation task in this
session; no new pytest run or full-suite result is claimed here.

Existing implementation-stage integrity findings: 23 saved evidence snapshots
validated; all 81 pre-existing output files retained their sizes and SHA-256
values; source arrays remained unchanged; independent numerical checks matched
saved counts, differences, peak identities and spherical distances.

For this record, standard-library file reads and hashing independently confirmed
that **all 23 source-artifact hash/size records and all 7 direct-code hash/size
records** still match the accepted JSON provenance. No framework or diagnostic
module was executed for these checks. This is not a new revalidation of detector
algorithms or the full evidence-contract loader. External raw TEC/GIM/catalog
files were not opened or rehashed. Hash consistency does not authenticate source
origin, original raw-data custody, OS isolation or trusted human authorization.

## 7. Scientific acceptance boundaries

- Great-circle **grid-center membership** is the accepted primary rule. It does
  **not** reproduce the historical visual grid-cell/circle overlap rule.
- The magnitude-radius relation is a literature-motivated retrospective
  reference, not a validated physical TEC influence boundary.
- Only **three coarse-grid centers** are included. Observations are spatially
  correlated, and nominal cells may cross the boundary. No true EPZ areal
  coverage or grid-cell intersection was calculated; intersection remains a
  future sensitivity analysis.
- Grid-hour sums are **not unique UTC anomaly hours**. Regional percentages are
  **unweighted descriptive means**, not areal coverage or earthquake association
  probabilities.
- Effective detector-valid counts are unavailable (`null`). Finite-input counts
  remain availability diagnostics and never replace the original denominators.
- **Kp, Dst and F10.7 were not evaluated.**
- Earthquake association, spatial statistical significance, physical causality
  and precursor identification are **not established**.

Acceptance changes none of the scientific definitions, parameters, selections,
Legacy references or saved outputs, and authorizes no Agent tool integration.

## 8. Checkpoint file inventory

Recommend committing **only**:

1. `docs/day5_epicentral_zone_diagnostic_scope.md`
2. `docs/day5_epicentral_zone_diagnostic_validation.md`
3. `examples/diagnose_afghanistan_epicentral_zone.py`
4. `tests/workflow/test_diagnose_afghanistan_epicentral_zone.py`

Read-only `git status --short`, `git branch --show-current` and
`git tag --list "epz-diagnostic-v1"` inspections used a per-command
`safe.directory` setting for the local ownership check, without changing global
configuration. Branch: `agent/day5-controlled-host`; current HEAD:
`0189f575fc7596fa0e11d3c20979a9d02633dc76`. The proposed tag is **absent**.
The four checkpoint files are untracked; nothing was staged.

Both diagnostic JSON outputs are ignored by Git, confirmed with
`git check-ignore`, and must remain local. No ignored scientific outputs, arrays,
images or caches belong in this checkpoint. This task created only this document.

## 9. Recommended commit and annotated tag

- Proposed commit: `docs(spatial): checkpoint EPZ diagnostic v1`
- Proposed **annotated** tag: `epz-diagnostic-v1`
- Suggested annotation: `EPZ Diagnostic V1 accepted for case-specific descriptive scientific analysis; see validation record for boundaries.`

Recommendations only: no staging, commit, push, tag or PR was performed. No
framework/model/API/protected execution, dependency or algorithm changes, Agent
integration, or accepted-file modification occurred in this task.

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```

Stop point: **Scientific & Security Review**. Await researcher-controlled Git
checkpoint creation.
