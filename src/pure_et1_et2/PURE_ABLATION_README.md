# Pure ET1 / ET2 framework ablation

A six-mode comparison: Single ST, ET1, ET2 and Double Compact ST, ET1, ET2.
All guided-pivot flags are disabled for the `pure` matrix. The Double
implementation has a fixed-budget optional adjacency bitmap with an exact
hash fallback to avoid very large dense index allocations.

```bash
python3 packages/MBE_PURE_ET1_ET2.zip selftest --cases 50 --modes single_st,single_et1,single_et2,double_compact_st,double_compact_et1,double_compact_et2
python3 packages/MBE_PURE_ET1_ET2.zip all data_clean/youtube.txt --modes pure --repeats 5 --out youtube_pure.csv
```

For the separate guided comparison choose `--modes guided`. Matching and
degree-two direct solvers generate outputs in different residual graph objects
on the two frameworks; do not present raw cross-framework search times as
comparable without a common timer contract.
