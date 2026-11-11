# Cleaned input graphs

The dataset archive contains 13 cleaned bipartite graphs, each beginning with a three-integer metadata header `nL nR m`. The following lines contain edges. The header is not an edge.

The complete canonical archive is split into six pieces in `parts/` because browser uploads limit file size; each part is at most 20 MiB. `ARCHIVE_PARTS.json` records the exact part sizes and SHA-256 values, and `COLLECTED_INPUT_SHA256.csv` records the SHA-256 of each extracted graph. `GRAPH_STATISTICS.csv` records vertex and edge statistics.

Run from the repository root:

```bash
python3 scripts/prepare_data.py
python3 scripts/verify_artifact.py
```

The reconstructed `CLEANED_GRAPH_FILES.zip`, `data_clean/`, and generated `outputs/` are excluded from version control. No benchmark result files are bundled in this release.

**Before public redistribution**, confirm each original dataset's license/terms and provide appropriate attribution. Fixed input hashes prove identity, not permission to redistribute the content.
