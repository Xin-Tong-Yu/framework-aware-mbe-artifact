# Cleaned input graphs

The dataset archive contains 13 bipartite graphs downloaded from [KONECT](https://konect.cc/) and converted to the benchmark's input format. The data preparation was reported as a **format-only conversion without intentional deletion or sampling of graph records**. Each file begins with a three-integer metadata header `nL nR m`; subsequent lines contain left/right vertex ID pairs. The header is not an edge. See `SOURCE_ATTRIBUTION.md` at the repository root for the KONECT reference and redistribution terms.

The complete canonical archive is split into six pieces in `parts/` because browser uploads limit file size; each part is at most 20 MiB. `ARCHIVE_PARTS.json` records the exact part sizes and SHA-256 values, and `COLLECTED_INPUT_SHA256.csv` records the SHA-256 of each extracted graph. `GRAPH_STATISTICS.csv` records vertex and edge statistics.

Run from the repository root:

```bash
python3 scripts/prepare_data.py
python3 scripts/verify_artifact.py
```

The reconstructed `CLEANED_GRAPH_FILES.zip`, `data_clean/`, and generated `outputs/` are excluded from version control. No benchmark result files are bundled in this release.

The SHA-256 manifests document the exact reformatted experimental inputs. They are not hashes of the original KONECT archives and do not by themselves prove source-to-converted record equality. Third-party reuse information is in the repository-root `SOURCE_ATTRIBUTION.md`.
