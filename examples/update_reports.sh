#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(readlink -m "${0%/*}")"

pushd "$SCRIPT_DIR" > /dev/null

# source environment variables, activate virtualenv, etc.
# shellcheck disable=SC1091
. .source

mkdir -p results/new
mkdir -p /var/www/reports/nightly-coverage

# fetch the latest nightly results
report-aggregator --log-level info nightly --results-dir results/new --timedelta-mins 2100
# publish the latest nightly results
report-aggregator --log-level info publish --results-dir results/new --web-dir /var/www/reports
# publish the latest nightly CLI coverage stats
report-aggregator --log-level info publish-coverage --results-dir results/new --web-dir /var/www/reports/nightly-coverage
