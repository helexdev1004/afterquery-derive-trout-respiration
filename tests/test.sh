#!/usr/bin/env bash
# The reward starts at 0 and becomes 1 only after pytest has passed every check.
set -uo pipefail
mkdir -p /logs/verifier
chmod 700 /logs/verifier 2>/dev/null || true
printf '0' > /logs/verifier/reward.txt
cd /tests || exit 0
if python -m pytest -q -p no:cacheprovider --ctrf /logs/verifier/ctrf.json test_night.py; then
  printf '1' > /logs/verifier/reward.txt
fi
exit 0
