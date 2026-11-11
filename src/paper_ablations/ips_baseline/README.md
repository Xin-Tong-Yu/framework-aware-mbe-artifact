# Published IPS and native-state ablations

**Source modules:** `framework_ablations/IPS-main/`, `IPS_ST_13DATA_2026/`, and `IPS_ST_ABLATION_13DATA/`.

This study uses the published IPS counting/aggregation reporting protocol and its native state-representation variants, not the explicit per-biclique output protocol used by the other framework comparisons.

Commands:

```bash
bash scripts/run_paper_ablations.sh ips-native-baseline --runs 5 --timeout 1200
bash scripts/run_paper_ablations.sh ips-native-ablation --runs 5 --timeout 1200
```

Do not combine IPS-native timing values with output-materializing modes in a single unrestricted ranking.
