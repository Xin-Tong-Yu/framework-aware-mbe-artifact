# Manuscript ablation implementations

The additional C++ and Python campaign sources are provided in the pinned archive
`MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip`, stored alongside this README. Each subdirectory here explains the scientific comparison and how to launch it; the complete executable implementation is in the source archive.

The archive is checked against SHA-256:

`c6d1d8586cb5dff16ed3b87f35379e0c77e13a6533eb53774c26f6798ecb8995`

## Installation

From the repository root:

```bash
python3 scripts/prepare_data.py
python3 scripts/verify_artifact.py
python3 scripts/setup_paper_ablations.py --check-only
python3 scripts/setup_paper_ablations.py
bash scripts/run_paper_ablations.sh check-source
```

The setup script checks archive integrity, extracts the native source suite to
`outputs/paper_suite/framework_ablations/`, and creates a link to the canonical thirteen graph inputs. This staging operation does not perform a benchmark and does not modify input files.

## Experiment commands

```bash
# Single Candidate Tree representation and traversal
bash scripts/run_paper_ablations.sh candidate --runs 5 --timeout 1200

# Single Result Tree layout x compressed reporting
bash scripts/run_paper_ablations.sh result-cr --runs 5 --timeout 1200

# Double Vector/Compact representation and terminal controls
bash scripts/run_paper_ablations.sh double-2x2 --runs 5 --timeout 1200

# Single/Double ST, ET, ET+TG
bash scripts/run_paper_ablations.sh six-mode --runs 5 --timeout 1200

# Published IPS and IPS-native state studies (count aggregation)
bash scripts/run_paper_ablations.sh ips-native-baseline --runs 5 --timeout 1200
bash scripts/run_paper_ablations.sh ips-native-ablation --runs 5 --timeout 1200
```

The underlying `framework_ablations/run_experiments.sh` dispatches each command to the corresponding original campaign runner. It also supports `oracle 20`, `single-baseline`, and `build-core`.

## Scientific interpretation

Candidate Tree, Result Tree, compact state, and direct termination tests isolate different implementation factors. Their internal timers are not universally comparable. In particular, the published IPS native experiment uses a count-aggregation protocol rather than explicit per-biclique output. Report within-campaign comparisons with the exact switches, datasets, repetition counts, and machine environment.

For the whole-paper study map, see [EXPERIMENT_COVERAGE.md](../../EXPERIMENT_COVERAGE.md).
