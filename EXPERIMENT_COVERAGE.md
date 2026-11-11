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

For a lightweight native correctness test, use `bash scripts/run_paper_ablations.sh oracle 20`. The two direct Python-ZIP runners also provide `selftest` commands in the root README.

## Interpretation and result protocol

**Output verification.** The four-mode MBET comparison uses aligned counts and order-independent XOR/SUM fingerprints. The unguided ET study checks output counts and framework-specific fingerprints; `scripts/validate_pure_csv.py` checks complete block/mode coverage. These checks do not replace mathematical correctness arguments for enumeration.

**Timing.** Single and Double internal search timers may cover different portions of processing. The MBET-family, guided ablations, pure-ET study, and native IPS count-aggregation comparison also have experiment-specific reporting contracts. Compare timings within matched runs of the same study and report compiler and machine information.

**Input integrity.** The graph files use `nL nR m` as their header; it is not an edge. SHA-256 manifests identify the exact canonical inputs. The archive part manifests permit byte-for-byte reconstruction from GitHub.

**Generated results.** The repository ships sources, exact input graphs, and experiment drivers; per-run measurement CSVs and machine-specific logs are produced when running the commands and are not stored in Git.
