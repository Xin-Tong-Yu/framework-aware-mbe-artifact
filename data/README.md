# Cleaned input graphs

The dataset archive contains 13 simple bipartite graphs derived from KONECT records. Each file begins with a three-integer graph-size header `nL nR m`. Subsequent lines contain left/right vertex ID pairs. [KONECT](https://konect.cc/) · [Source attribution](../SOURCE_ATTRIBUTION.md)

The complete canonical archive is split into six pieces in `parts/` because browser uploads limit file size. Each part is at most 20 MiB. `ARCHIVE_PARTS.json` records the part sizes and SHA-256 values. `COLLECTED_INPUT_SHA256.csv` records both the SHA-256 of each extracted graph and the Candidate Tree edge-list digest after dropping the header and writing each ordered edge as two decimal integers separated by a tab and ending in LF. `python3 scripts/verify_artifact.py --full-scan` recomputes both digests. `GRAPH_STATISTICS.csv` records vertex and edge statistics.

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

The canonical Ukrainian Wikiquote file (`ukwiki.txt`) declares 779 and 16,699 vertices. The edges cover
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

| Graph | KONECT input |
| --- | --- |
| FR | [UC Irvine forum](https://konect.cc/networks/opsahl-ucforum/) |
| WK | [Ukrainian Wikiquote edits](https://konect.cc/networks/edit-ukwikiquote/) |
| ES | [Escorts](https://konect.cc/networks/escorts/) |
| YT | [YouTube group memberships](https://konect.cc/networks/youtube-groupmemberships/) |
| GH | [GitHub](https://konect.cc/networks/github/) |
| BC | [BookCrossing implicit interactions](https://konect.cc/networks/bookcrossing_full-rating/) |
| SO | [Stack Overflow favorites](https://konect.cc/networks/stackexchange-stackoverflow/) |
| AC | [Actor–movie network](https://konect.cc/networks/actor-movie/) |
| TW | [Twitter user–hashtag network](https://konect.cc/networks/munmun_twitterex_ut/) |
| BS | [BibSonomy tag–item network](https://konect.cc/networks/bibsonomy-2ti/) |
| IM | [IMDb via Pajek](https://konect.cc/networks/actor2/) |
| AZ | [Amazon ratings](https://konect.cc/networks/amazon-ratings/) |
| DB | [DBLP author–publication network](https://konect.cc/networks/dblp-author/) |

## Rebuild from KONECT archives

Place the locally acquired archives named in the source map in a directory.
The extractor checks each archive SHA-256, streams the specified `out.*`
member, and publishes it after its SHA-256 matches. The converter and
canonical verifier then check the normalized graphs. Run from the repository
root under Linux or WSL. [KONECT catalog](https://konect.cc/networks/) · [Source terms](../SOURCE_ATTRIBUTION.md#dataset-source-konect)

```sh
python3 src/data_preparation/extract_konect_edges.py /path/to/archives outputs/konect-raw
python3 src/data_preparation/clean_konect13.py \
  --src outputs/konect-raw --dst outputs/konect-rebuilt \
  --sorter gnu --sort-memory 96M --pad-isolates
python3 scripts/verify_artifact.py --inputs-only --data-dir outputs/konect-rebuilt --full-scan
```

On Windows, use `python` and `--sorter python` for the same byte format.
The isolate option applies to the two documented header adjustments. Use
`--graphs` for a subset in the extractor and verifier, and `--only` in the
converter. For the native ablation launcher, rebuild into `data_clean/`.
The pure ET launcher also accepts `DATA_DIR=outputs/konect-rebuilt`.
