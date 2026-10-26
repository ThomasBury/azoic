# M62: performance measurements and observed handoffs

M62 is **in progress**. The benchmark supplies engineering evidence. Acceptance
also needs unaided handoffs by two medior actuaries, one senior actuary and one
ML engineer. None has been observed yet; automated checks cannot replace them.
M62 stands alone under [PRD section 6](PRD.md#6-milestones).

## Reproduce the performance measurement

Use the locked checkout environment on Linux, from the repository root:

```bash
uv sync --all-extras --all-groups --locked
uv run python tests/benchmark_workflow.py --rows 1000000 --threads 1 --out /tmp/azoic-m62-million-1
```

Choose a new output directory for every run; existing directories are rejected.
The default is one million synthetic development rows, seed 42, 20 continuous
numeric predictors and 10 categorical predictors with eight integer levels each.
Exposure is uniform between half and one year. Poisson counts use exposure and
two numeric risk effects; amounts are counts times simulated Gamma severity.
There is no missingness, high-cardinality vocabulary or real portfolio data.
Periods 0–18 train; periods 19–23 provide development validation. There is no
final-test or actuarial model-approval claim in this performance workload.

The YAML fits one Tweedie log-link GLM after native tree binning/grouping, plus
one raw-feature Tweedie GBM with 50 trees, 15 leaves and learning rate 0.05.
It retains normal workflow validation, fingerprinting, diagnostics and provenance.
The preparation process writes the Parquet/YAML inputs. Separate fresh processes
then execute fit/save and load/resume; a fourth verifies their outputs. Generation,
imports, process startup and verification are outside the timed fit/resume totals.
Both timed processes load the same Parquet and score every row, write a card,
comparison and rates, and export the raw GLM workbook without recalibration.
Resume reuses saved diagnostics and forbids all native wrapper/preprocessor fits.

`fit.json` and `resume.json` record wall time by loading, preprocessing fit,
preprocessing transform, model fit, prediction, diagnostic calculation, final
assembly, persistence, reporting and workbook export. Stage calls are disjoint;
unattributed time includes orchestration, validation/splitting, frame selection
and output I/O outside those calls. Preprocessing fit counts are transformer API
calls, not the count of internal univariate trees. The benchmark uses local
instrumentation of the checkout, without production telemetry or API changes.

Each stage reports sampled **whole-process resident memory**, including retained
inputs/models and native libraries, at 10 ms intervals and call boundaries.
These are stage RSS estimates, not allocated-byte deltas; brief peaks can be
missed and RSS accounting is approximate. Separately, `process_peak_rss_mib`
records the process-lifetime kernel high-water mark, including imports. It must
not be read as a stage peak or added across stages. Linux reports `ru_maxrss` in
KiB; see the [Linux resource-usage manual](https://man7.org/linux/man-pages/man2/getrusage.2.html).

The parent sets OpenMP, OpenBLAS, MKL and NumExpr thread limits before worker
imports. Arrow CPU/I/O pools and GBM `n_jobs` use the requested limit; native
univariate preprocessing trees remain single-threaded. JSON records the observed
BLAS/OpenMP limits, Arrow pools, dependency versions, hardware, CPU affinity,
visible memory and source revision/status. The RSS sampler adds one monitoring
thread; configured pool limits do not count all process threads. Data generation
immediately precedes loading, so treat reads as potentially warm OS-page-cache
reads. No system cache is cleared and other desktop activity is uncontrolled.

`environment.json` counts avoided fitting and sums its measured fit seconds.
Fresh-process verification requires identical predictions, card/comparison bytes
and every workbook cell. Generated portfolios, artifacts, arrays, workbooks and
JSON remain under the supplied evidence directory, outside source control.
Optimized runs also record SHA-256 digests of the benchmark and production modules.
For a quick regression, use 500 rows or run:

```bash
uv run pytest tests/test_benchmark_workflow.py
```

### Recorded measurements — 2026-10-26

Observed on an Intel Core i5-7300U at nominal 2.60 GHz (two physical cores,
four hardware threads; affinity CPUs 0–3), Linux 6.8.0-142 x86-64/glibc 2.39,
15.29 GiB visible RAM, Python 3.12.7. All configured BLAS/OpenMP limits, Arrow
CPU/I/O pools and GBM `n_jobs` were one. The full suite and distribution smokes
ran afterward. Other desktop activity was uncontrolled; local `/tmp` reads
were potentially warm and storage hardware was not characterized.

The base revision was `5694715`; the baseline had the benchmark but unchanged
production code. The two optimized runs used the leaf-lookup change recorded in
this milestone. The workload fingerprint was
`0848b450b32f2afd0881e32d55549aeb3a1b06db551f4eaa3cb9807fd176c3b8`.
All runs used 1,000,000 rows: 791,667 training and 208,333 development-validation
rows. Runtime versions: NumPy 2.5.2, pandas 3.0.6, SciPy 1.18.0, scikit-learn
1.9.0, glum 3.4.1, LightGBM 4.7.0, Arrow 25.0.1; the recorded full environment
also includes Azoic's other runtime dependencies. These are local measurements,
not a promise for other portfolios, machines, versions or thread settings.

Fit/save plus the shared report/predict/export consumers:

| Stage | Baseline seconds | Optimized seconds, two runs | Optimized sampled peak RSS, MiB |
| --- | ---: | ---: | ---: |
| Loading | 1.68 | 1.46–1.58 | 767.5–767.7 |
| Preprocessing fit | 10.28 | 10.19–10.38 | 1725.7–1731.3 |
| Preprocessing transform | 44.18 | 17.63–19.66 | 1757.9–1758.4 |
| Model fit | 15.35 | 15.37–16.75 | 1423.3–1423.9 |
| Model prediction | 8.18 | 7.05–7.30 | 1304.7–1307.6 |
| Diagnostic calculations | 0.62 | 0.60–0.63 | 1304.7–1307.6 |
| Final assembly | 0.87 | 0.81–0.85 | 975.5–976.0 |
| Save fitted candidates | 0.06 | 0.05–0.06 | 975.5–976.0 |
| Card/comparison construction | 0.01 | 0.01 | 975.5–976.0 |
| Workbook export | 0.28 | 0.26–0.28 | 1061.6–1062.1 |
| Unattributed orchestration/I/O | 1.13 | 1.14–1.38 | — |
| **Timed total** | **82.63** | **54.78–58.68** | — |

Process-lifetime peak RSS was 1761.97 MiB before and 1757.39–1757.83 MiB
afterward. RSS estimates can slightly exceed kernel high-water accounting;
these results establish no material memory reduction.

Fresh-process saved consumers, without fitting or recomputing diagnostics:

| Stage | Optimized seconds, two runs | Optimized sampled peak RSS, MiB |
| --- | ---: | ---: |
| Loading scoring inputs | 2.28–2.50 | 767.3–767.9 |
| Load fitted candidates | 0.18–0.19 | 859.3–859.9 |
| Card/comparison construction | 0.01–0.02 | 867.6–868.1 |
| Preprocessing transform | 6.43–7.19 | 1287.3–1287.7 |
| Model prediction | 3.55–3.64 | 1097.7–1098.1 |
| Workbook export | 0.26–0.30 | 1030.0–1030.5 |
| Unattributed orchestration/I/O | 0.06–0.07 | — |
| **Timed total** | **12.78–13.90** | — |

The baseline resume total was 27.00 s, including 18.70 s transforming inputs.
Optimized process-lifetime peak RSS was 1286.87–1287.57 MiB. Ranges above are
two observations per stage, not confidence intervals or an additive range total.
Saved consumers avoided **two transformer API fits and two model fits**,
25.56–27.13 s of fitting on these optimized runs, plus their training/validation
transformation, prediction, diagnostic and assembly work. The total difference
between operations is not all avoided fitting.

Corresponding rates across three fit/resume pairs agreed exactly (twelve million
values checked); reports agreed after normalizing input paths, and every workbook
cell agreed. Within each pair, reports were byte-identical without normalization.
A baseline saved GLM also retained exact million-row predictions under the new
transformation code. A 100,000-row profile identified the per-row leaf mapping
loops; replacing them with per-call lookup arrays preserved fitted state, native
routing, boundaries and typed categories. No transformation cache was added:
after this change transforms were below combined fitting time, and saved consumers
already avoid relearning. There is no demonstrated repeated-training cache use
case here to justify partition/configuration invalidation machinery.

Full inputs/outputs are in `/tmp/azoic-m62-million-{1,2,3}`. Retained small
measurement records are under ignored `evidence/m62/measurements/2026-10-26/`.
This benchmark covers compact model cards/comparisons and the direct workbook;
large raw-segment tariff-review bundles, tuning, frequency-severity, production
bundles, high cardinality and missing-heavy data were not performance-measured.
No receiving engine, Windows performance or user-observation claim follows.

Verification: locked all-extras/groups sync, Ruff/Ty and **1,512 tests** passed
(4 skips, 2 expected failures); the strengthened mixed integer/tuple-label cases
also passed separately. Strict docs, wheel/sdist builds and both runtime-only
Python 3.12 artifact smokes passed. No dependencies, API or starter blocks changed.

## Run the observed handoffs

The user confirmed that participants are not available yet. Recruit actual
practitioners for the four roles below; record experience and familiarity with
Azoic using anonymous participant IDs. Do not count an agent, scripted smoke,
maintainer walkthrough or facilitator-assisted completion as unaided acceptance.

| Participant | Status | Handoff |
| --- | --- | --- |
| Medior A | Not recruited | First Python GLM/GBM comparison and raw GLM workbook |
| Medior B | Not recruited | Reserved final membership, YAML candidates, saved state and controlled revision |
| Senior actuary | Not recruited | Explain, challenge and select from development tariff-review evidence |
| ML engineer | Not recruited | Frozen final evaluation, explicit production refit and batch-scoring handoff |

### Facilitator preparation

Use a clean directory for each participant and the same recorded checkout/lock.
Install dependencies in advance; separately record any setup performed by the
participant. Provide normal docs/search/CLI help. Record whether another AI or
colleague supplied help; that attempt is assisted. Obtain agreement to observation
and any recording. Keep identity/contact details separate from technical evidence.

Use the network-free synthetic [first-model recipe](docs/getting-started/first-model.md)
as the common small portfolio. The facilitator may run it once before sessions
to retain a pristine `portfolio.parquet`; do not give participants its fitted
outputs as their own work. Medior A starts with the recipe, Medior B with the
pristine portfolio. Use the existing
[portfolio membership guide](docs/guide/actuarial-workflow.md#freeze-portfolio-membership-before-experimenting)
to declare stable IDs and reserve the final periods **before** Medior B's
experiments. The senior receives Medior B's original and revised candidates,
original development frame and review bundle, without final outcomes. The ML
engineer receives the selected frozen saved artifact, unchanged development and
reserved final frames, predeclared membership and the senior's selection reasons.
If an upstream task fails, record a blocked downstream handoff; a facilitator
substitute may support a separate task attempt but cannot pass the end-to-end chain.

For review only, supply an explicitly synthetic incumbent technical rate of
400 EUR/year for each development ID, including one rate of zero. This is a
comparison assumption, not an actual incumbent or an estimate of market prices.
Use fresh output directories. Preserve complete source frames/indices/dtypes;
reconstructing them from edited CSV can invalidate fingerprints.

Before each task, explain only its outcome and supplied inputs. Start a timer
when the participant starts reading/working; record completion, abandoned work,
active minutes and elapsed minutes, excluding recorded breaks separately. Allow
up to 90 minutes per medior/engineer task and 60 minutes for senior review as
session scheduling limits, not product speed targets. A timeout is unfinished.
Observe without hints; when help is requested or necessary, timestamp the
exact intervention and mark the attempt assisted. Let participants explain their
interpretation before correcting misunderstandings after the attempt.

### Participant task cards and acceptance

1. **Medior A:** fit and compare the documented GLM and raw GBM; hand over
   diagnostics, rates and an Excel tariff. Explain which columns are predictors,
   how exposure enters fitting, rate versus period cost, what ranking and O/P
   each measure, and whether the workbook was recalibrated. Pass when the
   recipient can reproduce the rates and the participant makes those distinctions
   without hints. The synthetic example does not establish model superiority.
2. **Medior B:** reserve and save final-test membership before experiments; check
   a YAML config with explicit predictors; fit/save candidates; resume prediction,
   comparison and export from saved state. Change one age boundary through a
   fixed native mapping and refit a separate candidate. Override one factor with
   a reason and apply one recorded training calibration. Hand over the original,
   refitted and revised candidates plus a development review against the supplied
   incumbent. Pass when final rows remain unused, source candidates are preserved,
   reports use identical IDs/basis, revised workbook/Python rates agree, and the
   participant correctly explains which operations fit or recalibrate. Use the
   [configuration](docs/guide/experiment-configuration.md),
   [preprocessing](docs/guide/data-preprocessing.md) and
   [operations](docs/guide/operations.md) guides.
3. **Senior actuary:** review the supplied report without its author or notebook.
   Explain why rates changed, affected groups, exposure/claims support, raw versus
   calibrated/revised scales and zero-incumbent percentage changes. Identify
   uncertainty and missing evidence; declare a selected candidate and rationale,
   or a justified rejection. Pass when the decision is supported by retained
   tables and does not treat development comparisons as independent final evidence.
   Rejection can be a successful review; it blocks production approval until resolved.
4. **ML engineer:** in a fresh process, load the selected artifact and score the
   outcome-free quote inputs. Evaluate the frozen selection once using the
   predeclared final membership, then explicitly refit production on the exact
   original full-portfolio union. Export a new production bundle and execute its
   batch recipe on synthetic agreement cases. Pass when unrounded expected rates
   agree, exact/adjacent boundaries and missing/unseen rejection behavior are
   checked, predecessor final evidence remains attributed to the frozen fit,
   production metrics are full-training only, and the engineer explains trusted
   pickle/environment constraints and downstream deployment/rollback ownership.
   Use the [production handoff recipe](docs/guide/operations.md#freeze-final-evidence-then-refit-production-explicitly).
   Running the Python recipe does not demonstrate agreement with a real receiving engine.

### Evidence and repair loop

Keep actual observations under ignored `evidence/m62/`, with one directory per
anonymous participant/attempt. Retain outputs, terminal logs and the environment
revision/versions with an event CSV. Empty template:

```csv
participant_id,role,attempt,task,start_utc,end_utc,elapsed_minutes,active_minutes,outcome,help,misunderstanding,evidence_path,blocker,next_action
```

For each event, record the action/error, exact message without portfolio values,
time spent recovering, requested/provided help and a short verbatim explanation
when useful. Outcomes are `unaided-pass`, `assisted`, `unfinished` or `blocked`.
Retain failed attempts. Summarize failures, help, time and misunderstandings by
role; link each blocker to a minimal fix and a focused check. Repeat failed tasks
after fixes, preferably with a fresh practitioner to distinguish documentation
improvement from familiarity. Record both attempts; never silently upgrade an
assisted attempt. Completion requires all four unaided handoffs and resolution
of blocking failures, plus the project gates. Keep unobserved acceptance pending
in [PROGRESS.md](PROGRESS.md#current-focus); do not promise runtime or readiness.
