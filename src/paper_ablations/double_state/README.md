# Double state representation and terminal controls

**Source modules:** `framework_ablations/MBE_NEW_P0_20261109/` and `framework_ablations/MBE_FAST_FOUR_MODES/`, with shared Double engine material from `MBE_CORRECTED_13DATA/`.

This campaign compares Vector/Compact state representations and terminal/guidance toggles under its explicit-output protocol.

Run:

```bash
bash scripts/run_paper_ablations.sh double-2x2 --runs 5 --timeout 1200
```

Retain the original mode definitions; state storage and ET/TG are separate factors. The published IPS *native-count* protocol belongs to a different comparison and is not equivalent to explicit output generation.
