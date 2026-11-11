# Manuscript ablation source modules

These directories map the manuscript's separate ablation studies to the original frozen campaign modules. The full C++ and Python code is distributed as a **single source-only archive** named `MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip` in this directory. The archive has no cleaned graph copies, benchmark timings, or historical result files.

**Release status:** the pinned source archive has been uploaded to this directory. Its original campaign files passed an independent source-presence check. Full clean-clone experimental execution and final manuscript table matching remain to be validated.

The source archive should have SHA-256:

`c6d1d8586cb5dff16ed3b87f35379e0c77e13a6533eb53774c26f6798ecb8995`

## Setup

Restore the 13 input graphs first:

```bash
python3 scripts/prepare_data.py
python3 scripts/verify_artifact.py
```

With the source archive already present in this directory:

```bash
python3 scripts/setup_paper_ablations.py --check-only
python3 scripts/setup_paper_ablations.py
bash scripts/run_paper_ablations.sh check-source
```

The installer unpacks the archive under Git-ignored `outputs/paper_suite/` and links the cleaned inputs read-only by path; it does not rerun algorithms.

## Independent campaigns

```bash
bash scripts/run_paper_ablations.sh candidate --runs 5 --timeout 1200
bash scripts/run_paper_ablations.sh result-cr --runs 5 --timeout 1200
bash scripts/run_paper_ablations.sh double-2x2 --runs 5 --timeout 1200
bash scripts/run_paper_ablations.sh six-mode --runs 5 --timeout 1200
bash scripts/run_paper_ablations.sh ips-native-ablation --runs 5 --timeout 1200
bash scripts/run_paper_ablations.sh ips-native-baseline --runs 5 --timeout 1200
```

Some commands compile native binaries and may take substantial time. Check the individual module README and printed options before a full run. Never combine internal search times across frameworks or experiments with different reporting semantics.

The source bundle includes the existing campaign scripts and their original relative directory layout. `run_experiments.sh` is the authoritative dispatcher. Package provenance: `MBE_COMPLETE_EXPERIMENT_CODE_ENGLISH_20261111.zip` (framework_ablations paper-experiment subtree). Files selected for this source-only bundle have not been retuned or assigned new performance claims.

See [EXPERIMENT_COVERAGE.md](../../EXPERIMENT_COVERAGE.md) for the full manuscript-to-artifact checklist.
