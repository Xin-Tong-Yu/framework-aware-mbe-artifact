#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -eq 0 ]]; then
  cat <<'HELP'
Usage: bash scripts/run_paper_ablations.sh COMMAND [OPTIONS]

Commands:
  check-source
  oracle [N=20]
  build-core
  single-baseline
  candidate
  result-cr
  double-2x2
  six-mode
  ips-native-baseline
  ips-native-ablation

Example:
  bash scripts/run_paper_ablations.sh candidate --runs 5 --timeout 1200

All source modules are stored in the pinned src/paper_ablations ZIP.
HELP
  exit 0
fi

cmd="$1"
python3 scripts/setup_paper_ablations.py
SUITE="$ROOT/outputs/paper_suite/framework_ablations"

# The native oracle runner has a short per-mode execution timeout. Compile all
# required executables first so its timeout measures enumeration, not cold builds.
if [[ "$cmd" == "oracle" ]]; then
  need_build=0
  for exe in one_core one_inline two_st two_st_hybrid two_et two_et_tg two_et_tg_compact; do
    if [[ ! -x "$SUITE/MBE_FAST_FOUR_MODES/bin/$exe" ]]; then
      need_build=1
      break
    fi
  done
  if [[ "$need_build" == 1 ]]; then
    echo "[ORACLE_BUILD] Preparing native executables before timed checks"
    bash "$SUITE/MBE_FAST_FOUR_MODES/build.sh"
  fi
fi

exec bash "$SUITE/run_experiments.sh" "$@"
