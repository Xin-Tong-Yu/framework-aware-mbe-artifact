# Cleaned input graphs

The dataset archive contains 13 simple bipartite graphs derived from KONECT records. Each file begins with a three-integer graph-size header `nL nR m`. Subsequent lines contain left/right vertex ID pairs. [KONECT](https://konect.cc/) · [Source attribution](../SOURCE_ATTRIBUTION.md)

The complete canonical archive is split into six pieces in `parts/` because browser uploads limit file size; each part is at most 20 MiB. `ARCHIVE_PARTS.json` records the exact part sizes and SHA-256 values, and `COLLECTED_INPUT_SHA256.csv` records the SHA-256 of each extracted graph. `GRAPH_STATISTICS.csv` records vertex and edge statistics.

Run the following commands from the repository root.

```bash
python3 scripts/prepare_data.py
python3 scripts/verify_artifact.py
```

The reconstructed `CLEANED_GRAPH_FILES.zip`, `data_clean/`, and generated `outputs/` are excluded from version control.

## Source-to-input checks

The archived converter parses the first two integer fields and skips blank and
comment lines. Weight and time fields are discarded. It sorts the pairs in
numeric order and keeps one record per distinct pair. It assigns zero-based IDs
to the vertices on each side in first-encounter order while scanning these
pairs. It swaps the two columns when the first side has more incident vertices.

The canonical UKWiki file declares 779 and 16,699 vertices. The edges cover
all 779 left IDs and 16,679 right IDs. The canonical Escorts file declares
6,625 and 10,107 vertices, with one unused ID on each side. These isolate counts
match the archived converter's dimension adjustments. The extra isolated IDs
contribute to the graph dimensions and cannot belong to a biclique with both
sides nonempty.

All thirteen inputs were rebuilt from KONECT archives and matched the
canonical SHA-256 values byte for byte. The audit used five retained downloads
and eight archives obtained from KONECT. The source map records the archive and
raw edge file hashes, raw record counts, and numbers of repeated pairs collapsed.
For Forum, 33,720 raw records yield 7,089 distinct edges.
[Raw source map](KONECT_SOURCE_MAP.csv) · [Canonical input manifest](COLLECTED_INPUT_SHA256.csv)

## Rebuild from KONECT archives

The source map identifies the archives distributed by KONECT and the `out.*`
members expected by the converter. After checking the archive hashes and
extracting those members, place the edge files in one directory. The archived
converter and the canonical input verifier can then run from the repository
root under Linux or WSL. [KONECT network catalog](https://konect.cc/networks/)

```sh
python3 src/data_preparation/clean_konect13.py \
  --src outputs/konect-raw --dst outputs/konect-rebuilt \
  --sorter gnu --sort-memory 96M --pad-isolates
python3 scripts/verify_artifact.py --data-dir outputs/konect-rebuilt --full-scan
```

The isolate option applies to the two documented header adjustments. The
verifier checks the output against the canonical byte sizes and SHA-256 values.
