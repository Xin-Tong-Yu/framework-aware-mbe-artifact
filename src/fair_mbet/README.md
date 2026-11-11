# Fair MBET, MBETM, and optimized Single comparison

The four runnable modes are `mbet`, `mbetm`, `st_nocr`, and `st_cr`.
All four process every maximal biclique, count it, and compute the same
order-independent XOR and SUM fingerprints. Disk tuple output is disabled during
normal performance measurements. The graph reader supports a validated
three-integer graph header or a headerless two-column edge list.

Typical checks:

```bash
python3 runners/MBE_FAIR_MBET_2024.zip selftest --cases 30
python3 runners/MBE_FAIR_MBET_2024.zip bench data_clean/youtube.txt --modes mbet,mbetm,st_nocr,st_cr --repeats 5 --out youtube_fair.csv
python3 runners/MBE_FAIR_MBET_2024.zip batch --data-dir data_clean --modes mbet,mbetm,st_nocr,st_cr --repeats 5 --out-dir fair_13_results --resume
```

`st_nocr` and `st_cr` are build-specific variants. Confirm their compile flags
against the final manuscript configuration before citing the comparison.
