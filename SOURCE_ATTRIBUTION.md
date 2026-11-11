# Software and data attribution

This repository contains experimental implementations and comparative drivers for maximal biclique enumeration (MBE). Source code and graph inputs are described separately below.

## Algorithmic sources

- **MBET / MBETM:** *Maximal Biclique Enumeration: A Prefix Tree Based Approach*, IEEE ICDE 2024. The MBET-family experiment contains the original baseline representation and implementation variants.
- **IPS:** *Maximal Biclique Enumeration with Improved Worst-Case Time Complexity Guarantee: A Partition-Oriented Strategy*, ACM SIGMOD 2026. The IPS-native studies use a count-aggregation protocol, reported separately from explicit-output enumeration.
- **Single/Double framework variants:** Candidate Tree, Result Tree, state representation, and termination/guidance experiments are organized in `src/paper_ablations/`.

Original authors and other rights holders retain their applicable intellectual-property and license rights. Code attribution is not a substitute for the applicable upstream source licenses.

## Dataset source: KONECT

**All thirteen experimental graph datasets were downloaded from the [Koblenz Network Collection (KONECT)](https://konect.cc/)**, curated by Jérôme Kunegis. KONECT is the common acquisition source, although the original networks may have their own respective creators and citation requirements.

The data preparation performed for these experiments was described by the authors as a **format conversion only, without intentional deletion, sampling, or filtering of graph records**. The resulting bipartite edge-list files are presented in the format expected by the benchmark programs:

```text
nL nR m
left_vertex_id right_vertex_id
left_vertex_id right_vertex_id
...
```

The first line is graph metadata, not an edge. The files represent the same intended bipartite incidence relations as the downloaded source graphs. The repository includes exact checksums for the converted inputs, not the original KONECT downloads; therefore the provided hashes establish reproducibility of the experimental inputs rather than an independently audited record-by-record comparison with the source downloads.

The thirteen graph labels used in the experiments are: Forum, UKWiki, Escorts, YouTube, GitHub, BookCrossing, StackOverflow, Actors, Twitter, BibSonomy, IMDb, Amazon, and DBLP. The canonical converted input files are stored in six archive parts under `data/parts/`, with exact SHA-256 hashes in `data/COLLECTED_INPUT_SHA256.csv` and graph measurements in `data/GRAPH_STATISTICS.csv`.

### Citation

Jérôme Kunegis. **KONECT – The Koblenz Network Collection.** *Proceedings of the International Conference on World Wide Web Companion (WWW Companion)*, pp. 1343–1350, 2013.

- Project website: https://konect.cc/
- Official KONECT reference bibliography: https://github.com/kunegis/konect-handbook/blob/master/konect.bib
- KONECT handbook and format details: https://github.com/kunegis/konect-handbook

KONECT's project-software licensing is not a blanket license covering all third-party datasets. Redistribution and further use of individual graphs remain subject to their original providers' terms. Users should cite the original dataset publications as applicable.
