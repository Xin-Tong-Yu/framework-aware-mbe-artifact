#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -eq 0 ]]; then
  cat <<'HELP'
Usage: bash scripts/run_paper_ablations.sh COMMAND [OPTIONS]

COMMAND can be:
  check-source
  oracle
  candidate
  result-cr
  double-2x2
  six-mode
  ips-native-baseline
  ips-native-ablation
  build-core

Example:
  bash scripts/run_paper_ablations.sh candidate --runs 5 --timeout 1200

The pinned source-only archive is required under src/paper_ablations/.
HELP
  exit 0
fi

python3 scripts/setup_paper_ablations.py
SUITE="$ROOT/outputs/paper_suite/framework_ablations"
exec bash "$SUITE/run_experiments.sh" "$@"
