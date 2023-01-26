import os

REPORT_DOWNLOADED_SFILE = ".downloaded"
REPORT_PUBLISHED_SFILE = ".published"

COV_DOWNLOADED_SFILE = ".downloaded_cov"

STEPS_BASE = "step"
REPORTS_DIRNAME = "allure-results"
REPORTS_ARCHIVE = "allure-results.tar.xz"
TIMEDELTA_MINS = 48 * 60

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or ""
AUTH_HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
}
ORG_NAME = "input-output-hk"
REPO_SLUG = f"{ORG_NAME}/cardano-node-tests"
RESULTS_ARTIFACT_NAME = "allure-results"

COV_ARTIFACT_NAME = "cli-coverage"
COV_FILE_NAME = "cli-coverage.json"
