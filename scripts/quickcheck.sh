#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/prepare_data.py
python3 scripts/verify_artifact.py
python3 scripts/check_release.py
