#!/usr/bin/env bash
# run every test in the life OS. no dependencies, no network, no fixtures left behind.
#
#   ./run_tests.sh            # everything
#   ./run_tests.sh test_kb    # one module
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -gt 0 ]; then
  exec python3 -m unittest "$@" -v
fi

echo "life OS test suite"
echo "  test_semantics — what the numbers mean"
echo "  test_api       — auth boundary, guards, write flows"
echo "  test_kb        — knowledge-base structure, validator, search"
echo

# the test server would otherwise log every request into the middle of the report.
export LIFE_TRACKER_QUIET=1
exec python3 -m unittest discover -s . -p "test_*.py"
