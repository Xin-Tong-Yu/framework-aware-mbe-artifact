# Single Candidate Tree ablation

**Source module:** `framework_ablations/V63_MBET_CORE_SELECT/`

Compares the Candidate Tree child representations and cursor/pre-fork variants in the Single framework. The module includes `v63_run.py`, `v62_run.py`, `v57_run.py` and the corresponding Single C++ engine.

Run after installing the source bundle:

```bash
bash scripts/run_paper_ablations.sh candidate --runs 5 --timeout 1200
```

Do not mistake the historical V63 module identifier for a requirement to release every preceding version. Only the runner and dependent source needed for this matrix are staged.
