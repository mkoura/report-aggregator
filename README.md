# Cardano Node Tests reports aggregator

Aggregate results from multiple test runs and generate Allure reports.


## Setup

Installation steps:

```sh
make install
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

### Local runs

Copy artifacts to the publishing host with SCP or another tool, using this layout:

```text
my-testrun/
  01/
    allure-results.tar.xz
    cli_coverage.json
  02/
    allure-results.tar.xz
```

The source directory name becomes the testrun name. Each immediate subdirectory must contain
`allure-results.tar.xz`; `cli_coverage.json` is optional.

```sh
mkdir -p results/testruns
report-aggregator --log-level info local -d results/testruns -s my-testrun
report-aggregator --log-level info publish --results-dir results/testruns --web-dir /var/www/reports --aggregate
```

The importer leaves the source untouched and stores artifacts under
`results/testruns/local/my-testrun/<run>/`. Coverage files are stored as `cli-coverage.json`.
The Allure report is published to `/var/www/reports/local/my-testrun/`.
Local coverage is not published; coverage publishing remains a separate nightly operation.

Repeat imports skip identical artifacts and preserve publication markers. Different artifacts for an
existing run cause an error before any artifacts are copied; use a new run subdirectory or testrun
name instead. Additional run subdirectories can be imported into the same testrun.

With `--aggregate`, only new, unpublished runs are combined. Publishing additional runs replaces the
existing report with those new results while preserving Allure history, not previously published
test results. If there are no new results, the existing report is left untouched.

## Tests

Run the standard-library test suite from the activated virtual environment:

```sh
python -m unittest discover -s tests -v
```
