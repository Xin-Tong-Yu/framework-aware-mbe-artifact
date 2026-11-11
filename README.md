# Framework-Aware Search-State Optimization for Maximal Biclique Enumeration

## Code and input data (results-free release)

This repository contains **source code, runnable experiment entry points, and the exact cleaned inputs for 13 bipartite graphs**. It intentionally **does not contain precomputed experiment results, timing CSV files, machine-specific logs, or historical development versions**. Re-running a benchmark creates new results under the Git-ignored `outputs/` directory.

**Coverage:** this release can rerun (1) the four-mode MBET/MBETM versus optimized Single comparison and (2) the unguided Single/Double ST/ET1/ET2 ablation. It is a **verified-core subset**, not yet a complete artifact for every experiment described in the manuscript. In particular, the separately evaluated Candidate Tree Inline/Cursor/Pre-fork, Result Tree layout/CR, Double Vector/Compact and guided ET/TG campaigns still require their final matched source configurations before they can be claimed reproducible here. Do not describe this release as a complete all-tables EAB artifact.

### Contents

| Directory | Description |
|---|---|
| `src/fair_mbet/` | Readable MBET, MBETM, Single ST-noCR and ST+CR implementation |
| `src/pure_et1_et2/` | Readable Single and Double ST, ET1 and ET2 implementations, with bitmap-memory guard |
| `runners/` | Two directly executable Python ZIP packages containing the corresponding source and build runners |
| `data/parts/` | Six pieces of the cleaned-graph data archive; each under 25 MiB |
| `data/COLLECTED_INPUT_SHA256.csv` | Fixed SHA-256 and file-size manifest for all 13 inputs |
| `data/GRAPH_STATISTICS.csv` | Number of vertices, edges, and maximum degree for each input graph |
| `scripts/` | Data restoration, input integrity checks and release checks |

No `results/` folder is included. No compiled binaries are required in the repository.

### Requirements

- Linux or WSL2, Python 3.9+, `g++` with C++17 support and standard Unix tools. The original experiments were conducted with Ubuntu 24.04 and GCC 13.3.0.
- Single-threaded execution for comparison with the reported experiments; use the same CPU, compiler options, machine, memory settings and repetition protocol for meaningful speed comparisons.
- Large input graphs can require significant memory. A 256-MiB stack was used in the BibSonomy pure-termination campaign.

### 1. Restore the graphs and verify integrity

From the repository root:

```bash
python3 scripts/prepare_data.py
python3 scripts/verify_artifact.py
python3 scripts/check_release.py
```

`prepare_data.py` checks the committed graph archive parts, restores the 13 `data_clean/*.txt` files, and verifies their original SHA-256 values. The restored files and full combined archive are ignored by Git. `verify_artifact.py` independently checks the restored graph files and their three-integer headers. For a slower full edge-by-edge integrity and vertex-range check:

```bash
python3 scripts/verify_artifact.py --full-scan
```

The three integers on the first line of each graph are **metadata** (`nL nR m`), not an input edge. Each following line is a bipartite edge. The algorithms must not interpret the header as an extra edge.

### 2. Small-graph correctness self-tests

These commands compile the native C++ implementations and compare output sets on randomly generated small graphs:

```bash
python3 runners/MBE_FAIR_MBET_2024.zip selftest --cases 20
python3 runners/MBE_PURE_ET1_ET2.zip selftest --cases 20 \
  --modes single_st,single_et1,single_et2,double_compact_st,double_compact_et1,double_compact_et2
```

### 3. Reproduce the four-mode MBET-family comparison

All four modes share the same per-biclique count and XOR/SUM fingerprint semantics; disk tuple writing is disabled.

```bash
mkdir -p outputs
python3 runners/MBE_FAIR_MBET_2024.zip bench data_clean/youtube.txt \
  --modes mbet,mbetm,st_nocr,st_cr \
  --repeats 5 --out outputs/youtube_fair.csv
```

To run the full 13-graph campaign, with incremental saved runs:

```bash
python3 runners/MBE_FAIR_MBET_2024.zip batch \
  --data-dir data_clean \
  --modes mbet,mbetm,st_nocr,st_cr \
  --repeats 5 --timeout 7200 \
  --out-dir outputs/fair_13 --resume
```

### 4. Reproduce the unguided Single/Double ET1/ET2 ablation

The six modes compare ST, ET1 and ET2 within each framework while keeping termination guidance off. Single tests the candidate path–column missing-incidence graph; Double tests the missing-edge graph among candidate vertices. Their internal search timers do **not** necessarily have identical boundaries, so do not rank Single against Double using those internal times directly.

```bash
mkdir -p outputs/pure_13
python3 runners/MBE_PURE_ET1_ET2.zip all data_clean/youtube.txt \
  --modes pure --repeats 5 --out outputs/pure_13/youtube.csv
```

The runner accepts one graph per `all` call. A convenience launcher for all 13 graphs is included:

```bash
bash scripts/run_pure_13.sh
```

This launches only the documented six pure modes. It writes new results to `outputs/pure_13/` and retains per-graph logs. It skips an existing output CSV rather than silently overwriting it; remove an output CSV explicitly if you want to rerun that graph. For a different input directory set `DATA_DIR` and for a different output directory set `OUT_DIR` before launching.

### Reproduction and reporting protocol

- The MBET-family and pure-ET campaigns are separate; their compile, timer, and output-processing details are recorded in the corresponding ZIP runner sources.
- The default performance measurements exclude graph reading and native compilation from each runner's reported search time. Do not compare separately calibrated campaigns as if they used identical timing boundaries.
- No benchmark timings or claimed speedups are embedded as precomputed results in this repository. The code generates fresh CSV files when run.
- Reproduction of the paper's other ST/CR/ET/TG tables requires additional final experiment code not contained in this subset.

### Provenance and redistribution

The implementations adapt the published ICDE 2024 MBET and SIGMOD 2026 IPS algorithms. Read `SOURCE_ATTRIBUTION.md` and retain upstream notices and licenses. The graph inputs come from third-party datasets; **confirm that redistributing the cleaned graph bytes is permitted before making the six data parts publicly available**. The presence of the inputs in this staging package does not itself establish their redistribution rights. If that cannot be confirmed, publish the SHA-256 manifest plus documented source links and a deterministic cleaning/reconstruction workflow instead.

### Manuscript experiment coverage and result validation

See [EXPERIMENT_COVERAGE.md](EXPERIMENT_COVERAGE.md) for the table-by-table coverage inventory, and [src/paper_ablations/README.md](src/paper_ablations/README.md) for the additional manuscript ablation campaigns. Their original source modules are packaged in a small, pinned source-only ZIP. Until that ZIP is uploaded to `src/paper_ablations/`, those campaigns are **not yet executable from a clone**. This repository should not be described as a complete all-tables reproduction package until the source ZIP is uploaded, all drivers have been verified against the submitted figures, and third-party redistribution is cleared.

After the unguided 13-graph campaign finishes, each per-graph output can be checked for all six configurations, five blocks, consistent result counts and within-framework fingerprints:

```bash
python3 scripts/validate_pure_csv.py --graph youtube.txt outputs/pure_13/youtube.csv
```

The batch launcher now refuses to silently skip an existing incomplete CSV. This check is an internal consistency check, not an independent mathematical proof of maximality or completeness.

**Data availability check:** the canonical archive requires all six `data/parts/graph_data_000.part` through `graph_data_005.part` files. If any part is missing, `python3 scripts/prepare_data.py --check-only` will stop with an error; do not claim data restoration has passed until all six hashes match.

See `GITHUB_UPLOAD_GUIDE.md` and `RELEASE_CHECKLIST.md` before submitting the public repository URL.
