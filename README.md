# Cardano Node Tests reports aggregator

Aggregate results from multiple test runs and generate Allure reports.


## Setup

Installation steps:

```text
# create python virtual env
python3 -m venv .env
# activate python virtual env
. .env/bin/activate
# update python virtual env
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade wheel
python3 -m pip install --upgrade virtualenv
virtualenv --upgrade-embed-wheels
# install package
python3 -m pip install --upgrade --upgrade-strategy eager -e .
```

Copy files from example cron job from `examples` directory and edit them as needed. Namely it is needed to provide the `BUILDKITE_TOKEN` variable.
