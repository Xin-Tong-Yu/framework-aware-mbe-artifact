# Software and data attribution

This repository contains experimental implementations and comparative drivers for maximal biclique enumeration (MBE). Source code and graph inputs are described separately below.

## Algorithmic sources

- **MBET / MBETM.** *Maximal Biclique Enumeration: A Prefix Tree Based Approach*, IEEE ICDE 2024. The MBET-family benchmark rebuilds the published search implementations with the shared per-result count and fingerprint semantics. [Authors' MBET repository](https://github.com/Haizs/MBET)
- **IPS.** *Maximal Biclique Enumeration with Improved Worst-Case Time Complexity Guarantee: A Partition-Oriented Strategy*, ACM SIGMOD 2026. The IPS-native studies aggregate counts. The controlled Double variants process individual results with fingerprints. [Authors' IPS repository](https://github.com/wangkaixin219/IPS)
- **Single/Double framework variants:** Candidate Tree, Result Tree, state representation, and termination/guidance experiments are organized in `src/paper_ablations/`.

The MBET snapshot used for source comparison is `2ee4c564d188429bd45bbbf3b84649af5fed568c`.
The Table II bundle retains its timer header byte for byte and adapts the
graph reader, entry point, and MBET header for the benchmark reporting
contract. [Pinned MBET source](https://github.com/Haizs/MBET/tree/2ee4c564d188429bd45bbbf3b84649af5fed568c)

The IPS reference snapshot is `2922165992c430d5ec0c6bba1b64bc55131df411`.
The nine software and build files in both `source_official` copies under
`IPS_ST_13DATA_2026` and `IPS_ST_ABLATION_13DATA` match that snapshot byte for
byte. The Double code in the pure runner retains the upstream argument,
array, hash, heap, and I/O headers and adapts the graph, search engine, and
entry point.
[Pinned IPS source](https://github.com/wangkaixin219/IPS/tree/2922165992c430d5ec0c6bba1b64bc55131df411)

The checked upstream snapshots provide source and README files. Their
license and authorization records for redistribution remain to be confirmed
with the rights holders. [Repository licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

## Dataset source: KONECT

**All thirteen experimental graph datasets were downloaded from the [Koblenz Network Collection (KONECT)](https://konect.cc/)**, curated by Jérôme Kunegis. KONECT is the common acquisition source, although the original networks may have their own respective creators and citation requirements.

The archived converter used the first two fields of each edge record, merged repeated vertex pairs, compacted the IDs on each side, and placed the smaller incident side first. The benchmark format uses a size header followed by the distinct pairs.

```text
nL nR m
left_vertex_id right_vertex_id
left_vertex_id right_vertex_id
...
```

The first line is graph metadata. The canonical manifest identifies the thirteen inputs used by the benchmark. All thirteen were rebuilt byte for byte with the archived converter. The source map gives the archive and raw-member hashes, and the data guide documents the isolated vertices included in the UKWiki and Escorts headers. [Data guide](data/README.md) · [Raw source map](data/KONECT_SOURCE_MAP.csv)

The thirteen graph labels used in the experiments are: Forum, UKWiki, Escorts, YouTube, GitHub, BookCrossing, StackOverflow, Actors, Twitter, BibSonomy, IMDb, Amazon, and DBLP. The canonical converted input files are stored in six archive parts under `data/parts/`, with exact SHA-256 hashes in `data/COLLECTED_INPUT_SHA256.csv` and graph measurements in `data/GRAPH_STATISTICS.csv`.

### Citation

Jérôme Kunegis. **KONECT – The Koblenz Network Collection.** *Proceedings of the International Conference on World Wide Web Companion (WWW Companion)*, pp. 1343–1350, 2013.

- Project website: https://konect.cc/
- Official KONECT reference bibliography: https://github.com/kunegis/konect-handbook/blob/master/konect.bib
- KONECT handbook and format details: https://github.com/kunegis/konect-handbook

Use the per-network source links in the data guide to identify the original
provider and its applicable terms. [Network sources and local reconstruction](data/README.md#source-to-input-checks)

- The University of Kassel's BibSonomy SQL-dump agreement limits use to
  noncommercial research and restricts transfer to third parties. The public
  redistribution status of the specific KONECT-derived `bibsonomy-2ti` edge
  archive requires confirmation with the provider. [Dump access terms](https://www.kde.cs.uni-kassel.de/bibsonomy/dumps/) · [BibSonomy agreement](https://www.kde.cs.uni-kassel.de/bibsonomy/BibSonomy_Agreement.pdf)
- DBLP publishes its bibliographic metadata under CC0 1.0 with a secondary
  ODC-BY 1.0 license. [DBLP metadata license](https://dblp.org/faq/Under%2Bwhat%2Blicense%2Bis%2Bthe%2Bdata%2Bfrom%2Bdblp%2Breleased.html)
- Stack Overflow describes the CC BY-SA versions that apply to public
  contributions by date. The KONECT input represents user–post favorite
  relationships. [Stack Overflow content licensing](https://stackoverflow.com/help/licensing) · [KONECT Stack Overflow favorites](https://konect.cc/networks/stackexchange-stackoverflow/)
