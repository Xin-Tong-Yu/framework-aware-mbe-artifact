#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# != 2 ]]; then
    echo "Usage: bash scripts/run_state_and_guidance.sh CPU OUTPUT_DIRECTORY" >&2
    exit 2
fi
cpu="$1"
out="$2"
runs=5
timeout=7200
stack_kib=262144
taskset -c "$cpu" true
mkdir -p "$out"
out="$(cd "$out" && pwd)"

exec 9>"$out/campaign.lock"
flock -n 9 || { echo "Another process is writing to $out" >&2; exit 1; }
export PYTHONHASHSEED=0
ulimit -s "$stack_kib"

protocol="$out/protocol.txt"
current="$out/.protocol.pending"
{
    printf 'cpu=%s\nruns=%s\ntimeout=%s\nstack_kib=%s\n' "$cpu" "$runs" "$timeout" "$stack_kib"
    printf 'python_hash_seed=%s\n' "$PYTHONHASHSEED"
    uname -srmo
    awk -F: '/^model name/ { print $2; exit }' /proc/cpuinfo
    python3 --version
    g++ --version | sed -n '1p'
    sha256sum src/paper_ablations/MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip
} > "$current"
if [[ -f "$protocol" ]]; then
    if ! cmp -s "$current" "$protocol"; then
        echo "Measurement protocol changed. Use a new output directory." >&2
        exit 2
    fi
    rm -- "$current"
else
    mv -- "$current" "$protocol"
fi

python3 scripts/verify_artifact.py
python3 scripts/setup_paper_ablations.py --output-dir "$out"
suite="$out/framework_ablations"

if [[ ! -x "$suite/MBE_FAST_FOUR_MODES/bin/one_core" ]]; then
    taskset -c "$cpu" bash "$suite/MBE_FAST_FOUR_MODES/build.sh"
fi

taskset -c "$cpu" bash "$suite/run_experiments.sh" six-mode \
    --runs "$runs" --timeout "$timeout" --cpu "$cpu" --retry-failed
python3 scripts/summarize_state_and_guidance.py "$suite" vi "$out"

taskset -c "$cpu" bash "$suite/run_experiments.sh" double-2x2 \
    --runs "$runs" --timeout "$timeout" --cpu "$cpu" --retry-failed
python3 scripts/summarize_state_and_guidance.py "$suite" v "$out"

taskset -c "$cpu" bash "$suite/run_experiments.sh" candidate \
    --runs "$runs" --timeout "$timeout" --cpu "$cpu" --retry-failed \
    --modes st_only v63_inline_st v63_core_st v63_core_d
python3 scripts/summarize_state_and_guidance.py "$suite" iii "$out"

taskset -c "$cpu" bash "$suite/run_experiments.sh" result-cr \
    --runs "$runs" --timeout "$timeout" --cpu "$cpu" --retry-failed
python3 scripts/summarize_state_and_guidance.py "$suite" iv "$out"
