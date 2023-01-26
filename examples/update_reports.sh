#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(readlink -m "${0%/*}")"

pushd "$SCRIPT_DIR" > /dev/null

# source environment variables (BUILDKITE_TOKEN), activate virtualenv, etc.
# shellcheck disable=SC1091
. .source

mkdir -p results/new
mkdir -p /var/www/reports/nightly-coverage

report-aggregator --log-level info nightly-buildkite --results-dir results/new --timedelta-mins 2100
report-aggregator --log-level info publish --results-dir results/new --web-dir /var/www/reports
report-aggregator --log-level info publish-coverage --results-dir results/new --web-dir /var/www/reports/nightly-coverage
