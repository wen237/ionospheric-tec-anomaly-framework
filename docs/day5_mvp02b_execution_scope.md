# MVP-02B — proposed researcher-run execution scope

Date: 2026-11-10 (Asia/Taipei). **Implementation and non-executing validation complete; real execution awaits separate approval.**

## Changes and reuse

Added only [the case-specific comparison wrapper](../examples/compare_afghanistan_mvp_spatial.py),
[its synthetic tests](../tests/workflow/test_compare_afghanistan_mvp_spatial.py), and this scope report.
Created two authorized local-only selection records under ignored `outputs/`.
Existing MVP-01/02A source, scientific algorithms/contracts, Legacy Stage 2,
published outputs, patch backups and frozen references are preserved.
Final checks found all 41 baseline file hashes unchanged. Both new Python files
passed AST/whitespace checks; this report's links and selection pins were checked.
The two selection records are ignored by Git. No commit, push, PR or merge was made.

The wrapper follows the existing [Modern visual reproduction example](../examples/reproduce_afghanistan_spatial_visuals.py):
it calls `run_spatial_verification_from_modern_gim`, uses
`save_spatial_anomaly_plot(..., grid_orientation="canonical")` and
`_maximum_anomaly(..., grid_orientation="canonical")`. UTC selection validation
and original input hash checks reuse MVP-02A. No Preparation Manifest is made.
There is no Agent, service, registry, signer, Store, DecisionRecord or new authorization gate.

## Recorded choices (not trusted execution authorization)

All target bounds below are inclusive UTC samples.

| Experiment | Mode / window | Selection record | SHA-256 |
| --- | --- | --- | --- |
| A | Independent; May 28 00:00–June 1 23:00; 120 hours | `outputs/afghanistan_mvp02b_selections/experiment_a_reference_120h/selection_record.json` (16,934 bytes) | `ddc032ed73fc25aa8a82a233574a7fd28634f1fa58e7f3aa4b447be5d69bc464` |
| B | Saved candidate cluster 1; May 28 00:00–June 2 23:00; 144 hours | `outputs/afghanistan_mvp02b_selections/experiment_b_candidate_144h/selection_record.json` (24,657 bytes) | `eb85bb59a6c0710decc0bdde344a66e5b2f641a1e852e1965ff1705e6eab86f7` |

A rationale: **Reproduce the original published Vision Model and Selected Window Rule result as the historical scientific reference.**

B rationale: **Evaluate the new evidence-aware negative-anomaly candidate and compare its spatial verification against the original research reference.**

Both retain parent bundle `outputs/afghanistan_mvp01_review`, its five verified
artifact hashes and run-record SHA-256
`41fc97350d94622f15b454d89b70291fb68d362991ee29665b967d8d9c03abda`.
Cluster 1's saved bounds are unchanged; A exactly matches the historical reference.
Cluster 0 remains the valid, unexecuted June 11–13 candidate. Neither record claims
trusted approval or grants execution eligibility.

The records were created through MVP-02A after verifying complete required daily
filename coverage and original source hashes. A needs 20 daily files (May 13–June 1);
B needs 21 (May 13–June 2). Both use the same 360-hour reference interval:
May 13 00:00 through May 27 23:00 UTC. NPZ numerical validation is deferred to
the existing Modern loader during a separately approved run.

## Exact proposed execution

Function: `examples.compare_afghanistan_mvp_spatial.run_comparison`.
Scientific boundary: the existing
`src.workflow.modern_spatial_input_adapter.run_spatial_verification_from_modern_gim`.

Fixed parameters: reference_days=15, k=3.0, 24 samples/day, canonical ascending
physical latitude, explicit chronological daily-file lists. The owning daily
file supplies hours 00–23; no Legacy loader, rescaling or second latitude flip.
Both plots use event (33.020,69.464), M6.0, with optional Cartopy boundaries off
to avoid implicit network downloads. The existing A input (33.02,69.46) and
confirmed event metadata remain independently preserved in parent artifacts.

Common PowerShell arguments:

```powershell
$mvp02bArgs = @(
  '--selection-a', 'outputs/afghanistan_mvp02b_selections/experiment_a_reference_120h/selection_record.json',
  '--selection-b', 'outputs/afghanistan_mvp02b_selections/experiment_b_candidate_144h/selection_record.json',
  '--review-bundle', 'outputs/afghanistan_mvp01_review',
  '--modern-data-dir', 'C:\Users\Wen\Documents\GitHub\gim-data-tools\processed',
  '--output-dir', 'outputs/afghanistan_mvp02b_comparison'
)
```

Read-only check (performed successfully with these argument values):

```powershell
.\.venv\Scripts\python.exe -B -m examples.compare_afghanistan_mvp_spatial plan @mvp02bArgs
```

**Proposed command only — NOT executed; requires separate explicit approval:**

```powershell
.\.venv\Scripts\python.exe -B -m examples.compare_afghanistan_mvp_spatial run @mvp02bArgs
```

The selected-record metadata, parent bundle and all required original-source
hashes are rechecked immediately before each D call and again afterward.
Checks detect ordinary file changes; they are not authenticated OS custody
or a guarantee against hostile concurrent replacement.

Current reviewed runtime: Python 3.10.6, NumPy 2.2.6, Matplotlib 3.10.9.
Wrapper SHA-256:
`f42b0ff8d9aff4c9cc2ee563d3a97d3eb666389dcda9f699f881079ae14ac44c`.
The eventual experiment summaries record these versions and hashes of selected
scientific source files; they do not attest the entire interpreter/deployment.

### Verified input pins

Researcher-supplied data directory:
`C:\Users\Wen\Documents\GitHub\gim-data-tools\processed`.
The B set below contains the full A set plus June 2 (`codg1530.22i.npz`).
These current sizes/SHA-256 values match the original MVP-01 source declarations;
recorded source paths were not opened as instructions.

| Filename | Bytes | SHA-256 |
| --- | ---: | --- |
| codg1330.22i.npz | 216012 | `79c7caea20762440fd3923693a74169ceffc703531bbd0b5fdcc415626898811` |
| codg1340.22i.npz | 217972 | `b716fd1ff48d3616438b38e8ad1ccc3598aca3ce87fb75d8801d6940b132eaf3` |
| codg1350.22i.npz | 220605 | `4d5225e8bacae6987644f889db40d0cdd2412e7b96aa40fe5524bf433e63380b` |
| codg1360.22i.npz | 220534 | `c469acf5c5683d018949a5d3bf226da963cdfe7f37773a567c622afa4723eb3d` |
| codg1370.22i.npz | 221272 | `e9fac54210a5d2376df6740cbed20daaad1f78bc455e30df66bee8a1868f4a73` |
| codg1380.22i.npz | 220971 | `49c5c135de65555f0dbb9166ab2e54f98c0b358d4342339f5448aadbadb2a1d5` |
| codg1390.22i.npz | 223726 | `1e48221a8db4ca112715e742ce0991e9e79f4b834ca8f157905b0c44288c7440` |
| codg1400.22i.npz | 224884 | `00439fa79c74e30d19a1daa74017e5c03bac75a43be28f90a9f62f47204c22d5` |
| codg1410.22i.npz | 222757 | `1b074811cf94dd36d70755463a8eefa6bad9565e618fe034b962729f8b6e61e7` |
| codg1420.22i.npz | 221933 | `f057a5465d4dd9afb61c5dd600992920cd8803e73c3f66099a55d2655f97c5af` |
| codg1430.22i.npz | 219977 | `34a6c221c24e11ab152cbba72ec4df8216ee5490df30822e091a5b44a1953f09` |
| codg1440.22i.npz | 219234 | `cbd142452431dac3eaca2e61dbcb676bcbedeed92b2f260b9178f097be43aa35` |
| codg1450.22i.npz | 217560 | `d7b329be73fd15c1bdc8ea25d630785c235dcfa6febd5260f06e73ca96239bd6` |
| codg1460.22i.npz | 212360 | `168865f1d7a73f5cb90e76ce1b1be94d22ecf8405b2ea417e7ca0e3977418203` |
| codg1470.22i.npz | 214151 | `516ebd6438995499bfd53203659bd215299509344bf3b026b3f063b46466ec8f` |
| codg1480.22i.npz | 207678 | `fc94d56f13680e7fadc2923eebc0593f2305af4e084134283932faea6c99847f` |
| codg1490.22i.npz | 207740 | `3148db1325f2cdcf822033e6862f75744d16be19b9f41007ee316c679276cec7` |
| codg1500.22i.npz | 198901 | `e9ba2aff1673d0614785fced16f8327d54eba7a27274df8c57603fa8dcc56202` |
| codg1510.22i.npz | 201736 | `e9f50c9b11d6c88f76888fe3bbfc1f158d65d1904d6029f00301e25c14b05539` |
| codg1520.22i.npz | 193948 | `adac079aaaf0202ef4d969c772dacadb72a1f038ce0c020b64edd9ee1f3daa6c` |
| codg1530.22i.npz | 199864 | `867202d248063311e329d87f71556fad9c1731a9b2713cad017af411d9c8580d` |

## Dual-window output contract

The fresh root `outputs/afghanistan_mvp02b_comparison` **has not been created**.
A future approved run reserves it exclusively. Existing outputs are never
overwritten; partial failures are retained with failure/status metadata.

Each `experiment_a_reference_120h/` and `experiment_b_candidate_144h/` contains:

- An exact copy of its `selection_record.json`, original selection pin and parent references.
- `spatial_arrays.npz`: full positive/negative count and percentage-ratio matrices,
  latitude/longitude arrays, window_steps, the fixed ratio_denominator,
  target_input_finite_counts and initial_reference_input_finite_counts.
- `positive.png`, `negative.png`, `execution_status.json`,
  and `experiment_summary.json` with peaks, input names/sizes/hashes,
  scientific parameters, environment, source hashes and artifact pins.

At the comparison root: `comparison_plan.json`, `cellwise_differences.npz`,
`comparison_report.md`, and the final `comparison_summary.json`.
Differences are **B minus A** for every count/ratio cell and input-availability
count; ratio differences are percentage points. The fixed-denominator change
is recorded separately. Source grids must agree exactly.

D retains its original normalization by all 120/144 target hours. The added
finite-value counts describe input availability only. They are **not** effective
detector-valid counts, which the existing scientific result contract does not
expose; that field remains null. No percentile or anomaly algorithm is duplicated.

Experiment A records the existing future real-execution checks: 120 hours,
71 × 73 grid, 5,183 finite ratio cells, positive maximum 10% at
(-22.5,-155)/(-22.5,-150), negative maximum 85% at (30,70).
Any mismatch remains visible; no parameters/results are fitted.
Experiment B has no requirement to reproduce those percentages.
**No new real spatial result, map, peak or comparison statistic exists yet.**

## Executed synthetic verification

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/workflow/test_compare_afghanistan_mvp_spatial.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest tests/workflow/test_explicit_window.py tests/workflow/test_temporal_window.py tests/workflow/test_window_planning.py tests/workflow/test_planning_evidence.py -q -p no:cacheprovider
```

Final results: **13 passed in 68.07s**; **234 passed in 3.12s**.
An earlier run had 12 passes and one assertion failure: removing June 2 was
correctly rejected but changed A's extra-file inventory before B's missing-file
check, producing a different error message. The test expectation was corrected.
Unsigned-count differences were also checked to prevent subtraction wraparound.

Tests substitute harmless Modern D and plotting functions and label generated
temporary artifacts `test_double_only`. They verify the real call signature,
15/3 parameters, chronological files, canonical map arguments, hashes at the
computation boundary, stale/missing inputs, selection binding, fresh outputs,
full serialization, reference checks, cell-wise differences and repeatable bytes.
No actual D/Stage 2, signing, key generation, Store or authorization operation ran.
The full suite was not run because it contains those protected operations.

## Remaining boundary and recommendation

Implementation and selection recording are complete. Recommend reviewing this
exact scope, both immutable selection pins and output contract, then separately
approving an execution context for one researcher-run comparison.

Section 6 of the researcher's MVP-02B request expressly withholds real-execution
approval. Existing Windows/C2 deployment remains NO_GO/unverified; this wrapper
does not establish separate principals, trusted researcher authentication or
effective source custody. Those requirements are not waived by calling Modern D
directly or by a CLI subcommand. The researcher must determine/approve the
applicable execution environment before any real computation. No new signing,
Store or Windows setup is proposed here.

```text
Windows Local Isolation: NOT VERIFIED
Trusted Human Authorization: NOT VERIFIED
Execution Eligibility: FALSE
```

Stop at Scientific & Security Review before real Framework D execution.

