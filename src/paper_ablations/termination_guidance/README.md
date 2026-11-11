# Single/Double ST, ET, ET+TG

**Source module:** `framework_ablations/MBE_CORRECTED_13DATA/`

This is the six-mode guided termination campaign. It is distinct from the unguided ET1/ET2 comparison already available under `src/pure_et1_et2/`.

Run:

```bash
bash scripts/run_paper_ablations.sh six-mode --runs 5 --timeout 1200
```

Terminals in the two frameworks are implemented against different residual search objects. Compare within-framework ablation ratios; do not rank Single and Double by their differing internal search timer boundaries.
