# Cardano Node Tests reports aggregator

Aggregate results from multiple test runs and generate Allure reports.


## Setup

Installation steps:

```text
# create python virtual env
python3 -m venv .venv
# activate python virtual env
. .venv/bin/activate
# update python virtual env
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade wheel
python3 -m pip install --upgrade virtualenv
virtualenv --upgrade-embed-wheels
# install package
python3 -m pip install --upgrade --upgrade-strategy eager -e .
```

Copy files from example cron job from `examples` directory and edit them as needed. Namely it is needed to provide the `GITHUB_TOKEN` (or `BUILDKITE_TOKEN`) variable.


## Usage

For nightly results, see [update_reports.sh](examples/update_reports.sh).

Example for publishing results of on-demand testing job on Github:

```sh
# fetch results for testrun id '1.35.6rc2-default_mixed_01' (can be multiple jobs)
report-aggregator testrun -d results/testruns -n 1.35.6rc2-default_mixed_01
# aggregate resuls with the same testrun id and publish them
report-aggregator publish --results-dir results/testruns --web-dir /var/www/reports --aggregate
```
