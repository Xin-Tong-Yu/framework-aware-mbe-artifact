#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DATA_DIR="${DATA_DIR:-data_clean}"
OUT_DIR="${OUT_DIR:-outputs/pure_13}"
mkdir -p "$OUT_DIR"
# Use the stack size from the completed BibSonomy campaign.
ulimit -s 262144
for graph in forum ukwiki escorts youtube github bkcrossing stackoverflow actors twitter bibsonomy imdb amazon dblp; do
    input="$DATA_DIR/$graph.txt"
    output="$OUT_DIR/$graph.csv"
    if [[ -s "$output" ]]; then
        echo "[SKIP] $graph: nonempty CSV exists (remove it to rerun)"
        continue
    fi
    echo "[RUN] $graph"
    python3 runners/MBE_PURE_ET1_ET2.zip all "$input" \
      --modes pure --repeats 5 --out "$output" \
      2>&1 | tee "$OUT_DIR/$graph.log"
done
