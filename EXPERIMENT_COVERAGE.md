# Experiment coverage and reproducibility matrix

The repository contains the complete available code paths for the studies listed below, with their original build definitions and mode switches. All experiments use the thirteen cleaned graphs restored through `python3 scripts/prepare_data.py`. Commands are run from the repository root. Generated CSVs, logs, and native binaries stay in ignored output directories.

| Study | Compared configurations | Reproduction command |
|---|---|---|
| Input characterization | 13 bipartite graphs, exact inputs and graph metadata | `python3 scripts/verify_artifact.py --full-scan` |
| 2024 MBET-family comparison | MBET, MBETM, Single ST-noCR, Single ST+CR | `python3 runners/MBE_FAIR_MBET_2024.zip batch --data-dir data_clean --modes mbet,mbetm,st_nocr,st_cr --repeats 5 --timeout 7200 --out-dir outputs/fair_13 --resume` |
| Single Candidate Tree | Map/Inline, Cursor, and Pre-fork configurations | `bash scripts/run_paper_ablations.sh candidate --runs 5 --timeout 1200` |
| Single Result Tree and CR | Result Tree layout × compressed reporting | `bash scripts/run_paper_ablations.sh result-cr --runs 5 --timeout 1200` |
| Double state representation | Vector/Compact and controlled terminal/guidance configurations | `bash scripts/run_paper_ablations.sh double-2x2 --runs 5 --timeout 1200` |
| Single/Double termination guidance | ST, ET, ET+TG | `bash scripts/run_paper_ablations.sh six-mode --runs 5 --timeout 1200` |
| Unguided 1-/2-biplex | Single/Double ST, ET1, ET2; TG disabled | `bash scripts/run_pure_13.sh` |
| Published 2026 IPS comparison | Original IPS/native count-aggregation variants | `bash scripts/run_paper_ablations.sh ips-native-baseline --runs 5 --timeout 1200` |
| IPS state ablation | Count-aggregation state representation variants | `bash scripts/run_paper_ablations.sh ips-native-ablation --runs 5 --timeout 1200` |

## Setup and validation

```bash
python3 scripts/prepare_data.py
python3 scripts/verify_artifact.py --full-scan
python3 scripts/setup_paper_ablations.py --check-only
python3 scripts/setup_paper_ablations.py
bash scripts/run_paper_ablations.sh check-source
```

The source archive for the additional studies is `src/paper_ablations/MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip`; its SHA-256 is pinned and checked by `scripts/setup_paper_ablations.py`. The dispatcher `run_experiments.sh` in that archive retains the native source modules and compile settings for each study. The archive is extracted into `outputs/paper_suite/framework_ablations/`.

For a lightweight native correctness test, use `bash scripts/run_paper_ablations.sh oracle 20`. Run `bash scripts/run_paper_ablations.sh prefix-oracle` to verify Single's matching and nonmatching prefix solvers on two constructed 17-by-17 graphs. The check compares complete output sets against an exhaustive closure oracle, rejects duplicates, and checks that a restrictive answer cap takes the fallback path on the cycle fixture. The two direct Python-ZIP runners also provide `selftest` commands in the root README.

## Interpretation and result protocol

**Output verification.** The four-mode MBET comparison uses aligned counts and order-independent XOR/SUM fingerprints. The unguided ET study checks output counts and framework-specific fingerprints; `scripts/validate_pure_csv.py` checks complete block/mode coverage. These checks do not replace mathematical correctness arguments for enumeration.

**Timing.** Single and Double internal search timers may cover different portions of processing. The MBET-family, guided ablations, pure-ET study, and native IPS count-aggregation comparison also have experiment-specific reporting contracts. Compare timings within matched runs of the same study and report compiler and machine information.

**Input integrity.** The graph files start with the `nL nR m` header. SHA-256 manifests identify the exact canonical inputs. Both the split artifact archive and the documented conversion of the original KONECT archives reproduce all thirteen input files byte for byte. [Data guide](data/README.md)

**Generated results.** The repository ships sources, exact input graphs, and experiment drivers. Per-run measurements are kept separately from Git.

## Rebuilding Tables II and VII from the original measurements

With the original code-and-results ZIP and original Bitmap Guard runner ZIP, run:

```sh
dir=outputs/historical_paper_records
python3 scripts/rebuild_archived_tables.py \
  "$dir/MBE_GITHUB_CODE_AND_RESULTS_NO_DATA.zip" \
  "$dir/MBE_BIPLEX_PURE_1V2_BITMAP_GUARD.zip" "$dir/reconstructed"
```

The script checks 260 MBET-family and 390 pure ET records against the canonical input identities and reference counts. It checks that MBET-family executable hashes, flags, and run settings agree across graphs, and matches the Bitmap Guard runner ZIP to the per-graph recorded hashes. It emits the rows of Tables II and VII plus a JSON file with five paired ratios for each contrast, archive and CSV hashes, and the Table VII sensitivity analysis restricted to graphs with at least one second of median ST time in both frameworks. The MBET-family summary includes whole-process wall-time ratios from the same runs. The original pure records identify the runner ZIP. New replay manifests also identify each mode's binary.

For Double, the JSON retains the paired ET1 and ET2 branch counts where they
were recorded. The relative reduction uses ET1 calls as the reference. The
summary identifies graphs with fewer ET2 calls in all five blocks and which
of those have a slower ET2 paired median. That comparison also appears in the
subset with median ST time of at least one second in both frameworks.

Append `--evidence-zip MBE_Archived_Table_II_VII.zip` to export the verified
CSV files and summaries with a SHA-256 inventory. This snapshot contains
measurement records and checksums. Its README gives the command that
regenerates the tables using the recorded historical runner hash.

Generate the vector figure for the direct ET2/ET1 comparison from the
rebuilt summary. The manuscript figure was produced with Matplotlib 3.9.2.

```sh
python3 scripts/plot_et_pairs.py "$dir/reconstructed/summary.json" et_paired.pdf
```

## Rebuilding Tables IV and VI from the original aggregate report

The original aggregate ZIP preserves graph-level paired medians for the
Result Tree and guided-termination campaigns. Rebuild the table rows,
cross-graph geometric means, and direct Table VI policy ratios with:

```sh
dir=outputs/historical_paper_records
python3 scripts/rebuild_archived_aggregate_tables.py \
  "$dir/MBE_20261109_RESULTS_FOR_OVERLEAF.zip" "$dir/aggregates" \
  --evidence-zip "$dir/MBE_Archived_Table_IV_VI.zip"
```

The script verifies the original archive and CSV SHA-256. The optional
snapshot contains the exact original CSV, reconstructed tables, and checksum
inventory. Pass the extracted `combined_13_graph_metrics.csv` to the same
script to reproduce the tables from the snapshot. Each CSV value summarizes
within-graph paired blocks. The native drivers below collect independent
per-run records.

Compare the original medians with a completed five-block replay of Table IV
or VI using `scripts/compare_native_replay.py`. Pass the archive or its CSV
entry, the replay's `framework_ablations` directory, the lowercase table
number, and a JSON output path. An explicit `--graphs` subset uses only
those graphs for both geometric means. The report gives the two ratios and
their speedup difference in percentage points. It records the replay input
and binary identities alongside the archived source hash.

## Regenerating Tables III–VI from native checkpoints

Use a dedicated output directory and choose a logical CPU available to the
process. The runner executes the guided, Double representation, Candidate
Tree, and Result Tree experiments in sequence. It applies the recorded mode
definitions and five blocks on each of the thirteen canonical graph inputs.

```sh
dir=outputs/icde_eab_state_ablations
bash scripts/run_state_and_guidance.sh 0 "$dir" 2>&1 | tee state-and-guidance.log
```

The runner stages a verified source bundle under the output directory and
keeps the native binaries, reports, and checkpoints there. Repeat with the
same CPU, runtime environment, and directory to reuse completed blocks.
The runner checks its saved `protocol.txt` before resuming. A changed run
configuration uses a new output directory so the original records stay available.
The launcher reports each incomplete study and continues through the remaining
studies. It exits with a failure status if any table still lacks validated blocks.
For Table VI, a native failure or fingerprint mismatch stops work on that graph
and the driver continues with the remaining graphs. Resuming with
`--retry-failed` retains complete blocks by their original seeds and measures
the unresolved blocks again. The installer stages the revised driver over the
pinned archive. Earlier checkpoints remain compatible when their executable,
input, and run metadata match.
For Table III, the driver records the CPU, effective stack limit, timeout,
block count, mode flags, and randomization settings. It uses a monotonic clock
for the paired anchors and retains the requested stack allowance when it is
already at least 64 MiB. Earlier checkpoints remain readable by the table
summarizer. New measurements use a separate campaign directory when the older
checkpoint lacks the timing metadata required for resumption.
For Table V, the driver checks equal Vector/Compact branch counts in both
terminal settings before accepting each block. Every ST anchor also requires
a peak RSS record from GNU time. A failed block stops the current graph.
Resumption retains the other validated blocks by their original seeds.

Rebuild a specific table without rerunning the benchmark by passing its
Roman numeral in lowercase:

```sh
python3 scripts/summarize_state_and_guidance.py "$dir/framework_ablations" vi "$dir"
```

The summarizer checks graph identities, complete blocks, positive times,
reference counts, and compatible fingerprints. The fifth speedup column of
Table IV divides inline/no-CR by inline+CR search time in each block. The
archived aggregate report gives a +7.7% geometric mean for that comparison.
Table V additionally checks equal branch counts for each matched Vector/Compact
comparison. Its memory cells are medians of whole-process peak RSS over the
ten ST runs of each build. The JSON files include the raw paired ratios and
checkpoint hashes. Table V also records paired wall-time ratios. Table VI
reports direct added-policy
comparisons in its JSON. Each block divides the ET-only time by the ET with
policy time within the same framework. The published ST comparisons continue
to use interpolated ST anchors. The Double ST build still runs the matching
eligibility scan with the terminal solver disabled. The original aggregate
report retained per-graph medians for the direct comparisons. Their geometric
mean gains are −3.6% for Single prefix solving with deferral and +19.1% for
the Double matching-oriented pivot. Recovering the individual block ratios
requires raw checkpoints or a replay. Each LaTeX file contains the generated
table rows.

## Regenerating the unguided ET table

Run the thirteen-graph campaign and keep each CSV with its run manifest. Use
the following commands from the repository root. Choose an available CPU
if CPU 0 is outside the process's affinity mask.

```sh
taskset -c 0 env MBE2_OPT=O3 OUT_DIR=outputs/icde_eab_pure_13 bash scripts/run_pure_13.sh
python3 scripts/summarize_pure_csv.py outputs/icde_eab_pure_13 \
  --json outputs/icde_eab_pure_13/summary.json \
  --latex outputs/icde_eab_pure_13/table_rows.tex
```

The summarizer checks the runner and input hashes, the CSV hash, matching
execution settings across graphs, output fingerprints, and the reference
biclique counts from Table I. The JSON stores all five paired ratios per
contrast. The table uses the median ratio within each graph and the
geometric mean of those ratios across graphs. The direct ET2/ET1 contrast
is computed from the two times in each block.

The current pure runner source checkpoints complete paired blocks in
`.csv.checkpoint.json`. Resume with the same inputs, runner ZIP, mode
order, seed, and execution settings. The final CSV and manifest are
published after all blocks pass validation. Repeated publication uses
the saved blocks if a process exits between the two final file writes.
Run the interruption regressions in Linux or WSL with
`python3 -m unittest discover -s tests -p test_pure_resume.py`.

### Double eligibility-scan ablation

Double ST in the original pure campaign evaluates the degree-two eligibility
predicate before continuing ordinary recursion. The auxiliary `double-gate`
matrix compares no scan, a degree-one scan, and a degree-two scan with solving
disabled in all three modes. The ET1 and ET2 modes keep classic pivots and
per-result fingerprints, and provide paired comparisons against the same
scan threshold. The runner checks equal branch counts and zero terminal
calls in the three ST controls.

Run the supplemental matrix separately from the primary timing campaign.
YouTube is a short case, GitHub has a large output set, and DBLP is a large,
sparse input with comparatively short search time. Retain the derived runner
ZIP with its raw records.

```sh
dir=outputs/icde_eab_double_gate
python3 scripts/package_pure_gate.py "$dir/MBE_PURE_ET_GATE.zip"
ulimit -s 262144
for graph in youtube github dblp; do
  taskset -c 0 env MBE2_OPT=O3 MBE2_CACHE="$dir/build_cache" \
    python3 "$dir/MBE_PURE_ET_GATE.zip" all "data_clean/$graph.txt" \
    --modes double-gate --repeats 5 --out "$dir/$graph.csv" --resume
done
python3 scripts/summarize_double_gate.py "$dir" --json "$dir/summary.json"
```
