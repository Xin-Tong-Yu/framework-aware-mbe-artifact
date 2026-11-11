#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
DATA_DIR="${DATA_DIR:-data_clean}"
OUT_DIR="${OUT_DIR:-outputs/pure_13}"
mkdir -p "$OUT_DIR"

# Match the increased stack allowance used for the completed BibSonomy runs.
ulimit -s 262144

for graph in forum ukwiki escorts youtube github bkcrossing stackoverflow actors twitter bibsonomy imdb amazon dblp; do
    input="$DATA_DIR/$graph.txt"
    output="$OUT_DIR/$graph.csv"
    if [[ ! -f "$input" ]]; then
        echo "[ERROR] Missing input: $input. First run python3 scripts/prepare_data.py" >&2
        exit 1
    fi
    if [[ -e "$output" ]]; then
        if python3 scripts/validate_pure_csv.py --quiet --graph "$graph.txt" "$output"; then
            echo "[SKIP] $graph: complete and internally consistent 30-run CSV"
            continue
        fi
        echo "[ERROR] Existing CSV is incomplete or inconsistent: $output" >&2
        echo "Move it aside for inspection, then rerun the script." >&2
        exit 1
    fi
    echo "[RUN] $graph"
    python3 runners/MBE_PURE_ET1_ET2.zip all "$input" \
      --modes pure --repeats 5 --out "$output" \
      2>&1 | tee "$OUT_DIR/$graph.log"
    python3 scripts/validate_pure_csv.py --graph "$graph.txt" "$output"
done
