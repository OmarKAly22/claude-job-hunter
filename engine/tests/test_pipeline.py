import json
from datetime import date

from conftest import FakeChecker, FakeHttp

from job_hunter_engine.config import load_config
from job_hunter_engine.pipeline import latest_leads, run_search
from job_hunter_engine.verify import PageCheck

CONFIG = """
[search]
titles = ["Data Engineer"]
locations = ["Germany", "Berlin"]
max_age_days = 30

[[employers]]
name = "Acme"
ats = "greenhouse"
slug = "acme"

[[employers]]
name = "Broken"
ats = "lever"
slug = "broken"
"""

BOARD = {"jobs": [
    {"title": "Senior Data Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1000001",
     "location": {"name": "Berlin"}, "first_published": "2026-11-20T00:00:00Z", "content": "&lt;p&gt;Spark&lt;/p&gt;"},
    {"title": "Data Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1000002",
     "location": {"name": "Berlin"}, "first_published": "2026-11-22T00:00:00Z", "content": "x"},
    {"title": "Data Engineer II", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1000003",
     "location": {"name": "Berlin"}, "first_published": "2026-11-21T00:00:00Z", "content": "x"},
    {"title": "Sales Manager", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1000004",
     "location": {"name": "Berlin"}, "content": "x"},
    {"title": "Data Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1000005",
     "location": {"name": "Paris, France"}, "content": "x"},
]}


def test_run_exports_live_jobs_and_remembers(write_config):
    cfg = load_config(write_config(CONFIG))
    http = FakeHttp({"https://boards-api.greenhouse.io/v1/boards/acme/jobs": BOARD})
    checker = FakeChecker({
        "https://boards.greenhouse.io/acme/jobs/1000002": PageCheck("dead", "Closed sign: 'no longer available'"),
        "https://boards.greenhouse.io/acme/jobs/1000003": PageCheck("unverifiable", "Page had almost no text"),
    })
    result = run_search(cfg, http=http, checker=checker, today=date(2026, 11, 25))

    titles = sorted(j.title for j in result.live)
    # 1000003 could not be read, but Greenhouse listed it in this run: accepted as live via the ATS API.
    assert titles == ["Data Engineer II", "Senior Data Engineer"]
    api_job = next(j for j in result.live if j.title == "Data Engineer II")
    assert api_job.verification == "ats-api" and "Listed in greenhouse:acme API" in api_job.link_proof
    assert [j.reason for j in result.rejected] == ["Dead link: Closed sign: 'no longer available'"]

    acme, broken = result.reports
    assert (acme.found, acme.in_scope, acme.live, acme.dead) == (5, 3, 2, 1)
    assert not broken.ok and "404" in broken.error

    data = latest_leads(cfg)
    assert data and data["jobs"][0]["company"] == "Acme"
    assert json.loads(result.export_path.read_text())["summary"] == result.summary()

    # Second run: nothing new is handed over or checked again.
    checker2 = FakeChecker()
    result2 = run_search(cfg, http=http, checker=checker2, today=date(2026, 11, 26))
    assert result2.live == [] and checker2.checked == []


def test_limit_keeps_newest(write_config):
    cfg = load_config(write_config(CONFIG))
    http = FakeHttp({"https://boards-api.greenhouse.io/v1/boards/acme/jobs": BOARD})
    result = run_search(cfg, http=http, checker=FakeChecker(), today=date(2026, 11, 25), max_new=1)
    assert [j.url[-7:] for j in result.live] == ["1000002"]
    assert result.stopped_early
