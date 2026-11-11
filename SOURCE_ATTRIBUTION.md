# Software and data attribution

This repository contains experimental implementations and comparative drivers for maximal biclique enumeration (MBE). The source archive preserves the implementation modules used for the reported studies.

## Algorithmic sources

- **MBET / MBETM:** *Maximal Biclique Enumeration: A Prefix Tree Based Approach*, IEEE ICDE 2024. The MBET-family experiment contains the original baseline representation and the corresponding implementation variants.
- **IPS:** *Maximal Biclique Enumeration with Improved Worst-Case Time Complexity Guarantee: A Partition-Oriented Strategy*, ACM SIGMOD 2026. The IPS-native runs use a count-aggregation protocol, which is reported separately from explicit-output enumeration experiments.
- **Single/Double framework variants:** the additional Candidate Tree, Result Tree, state-representation, and terminal/guidance experiments are organized by study in `src/paper_ablations/`.

The relevant upstream algorithm credit, source headers, and notices are retained where supplied by the underlying implementations. This repository does not grant new rights to material owned by other parties.

## Graph inputs

Thirteen bipartite graph inputs are stored as a deterministic, segmented archive under `data/parts/`. The exact cleaned bytes are specified by `data/COLLECTED_INPUT_SHA256.csv`, and graph statistics are listed in `data/GRAPH_STATISTICS.csv`.

The input labels are: Forum, UKWiki, Escorts, YouTube, GitHub, BookCrossing, StackOverflow, Actors, Twitter, BibSonomy, IMDb, Amazon, and DBLP. The cleaned input files use a three-integer `nL nR m` header followed by bipartite edge pairs.

The original dataset providers and upstream code authors retain their applicable intellectual-property and license rights. The experimental archive and its checksum manifests describe the specific inputs and implementations; they do not independently license third-party content. Any reuse or redistribution must follow the original source terms.
