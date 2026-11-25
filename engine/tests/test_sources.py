from datetime import date

from conftest import FakeHttp

from job_hunter_engine.config import ArbeitsagenturConfig, Employer
from job_hunter_engine.sources import (
    enrich_smartrecruiters, enrich_workday, fetch_arbeitsagentur, fetch_ashby, fetch_greenhouse, fetch_lever,
    fetch_personio, fetch_recruitee, fetch_smartrecruiters, fetch_workday, workday_parts, workday_posted,
)


def test_greenhouse_unescapes_html_content():
    http = FakeHttp({"https://boards-api.greenhouse.io/v1/boards/acme/jobs": {"jobs": [{
        "title": "Senior Data Engineer (m/w/d)", "absolute_url": "https://boards.greenhouse.io/acme/jobs/4012345",
        "location": {"name": "Berlin, Germany"}, "updated_at": "2026-11-20T10:00:00-05:00",
        "first_published": "2026-11-18T09:00:00Z",
        "content": "&lt;p&gt;Build &lt;strong&gt;pipelines&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;",
    }]}})
    [job] = fetch_greenhouse(http, Employer("Acme", "greenhouse", "acme"), [])
    assert job.posted == date(2026, 11, 18)
    assert job.location == "Berlin, Germany"
    assert "Build pipelines" in job.description and "- Python" in job.description
    assert "<" not in job.description


def test_lever_eu_region_and_lists():
    http = FakeHttp({"https://api.eu.lever.co/v0/postings/acme": [{
        "text": "ML Engineer", "hostedUrl": "https://jobs.eu.lever.co/acme/abc-123",
        "categories": {"location": "Munich", "allLocations": ["Munich", "Remote - Germany"]},
        "createdAt": 1763900000000, "descriptionPlain": "About the role",
        "lists": [{"text": "Requirements", "content": "<li>PyTorch</li>"}], "workplaceType": "hybrid",
    }]})
    [job] = fetch_lever(http, Employer("Acme", "lever", "acme", region="eu"), [])
    assert job.location == "Munich, Remote - Germany"
    assert "PyTorch" in job.description and job.remote is False
    assert job.posted is not None


def test_ashby_skips_unlisted():
    http = FakeHttp({"https://api.ashbyhq.com/posting-api/job-board/acme": {"jobs": [
        {"title": "Data Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/1", "location": "Berlin",
         "publishedAt": "2026-11-01T00:00:00.000+00:00", "descriptionPlain": "x", "isListed": True, "isRemote": False},
        {"title": "Hidden", "jobUrl": "https://jobs.ashbyhq.com/acme/2", "isListed": False},
    ]}})
    jobs = fetch_ashby(http, Employer("Acme", "ashby", "acme"), [])
    assert [j.title for j in jobs] == ["Data Engineer"]


def test_smartrecruiters_pages_and_enrich():
    page1 = {"totalFound": 2, "content": [{"id": "111", "name": "Data Engineer", "releasedDate": "2026-11-10T00:00:00.000Z",
                                           "location": {"city": "Cologne", "country": "de", "remote": False}}]}
    page2 = {"totalFound": 2, "content": [{"id": "222", "name": "Analyst", "location": {"fullLocation": "Bonn, Germany"}}]}
    http = FakeHttp({
        "https://api.smartrecruiters.com/v1/companies/acme/postings?limit=100&offset=0": page1,
        "https://api.smartrecruiters.com/v1/companies/acme/postings?limit=100&offset=1": page2,
        "https://api.smartrecruiters.com/v1/companies/acme/postings/111": {"jobAd": {"sections": {
            "jobDescription": {"title": "Job", "text": "<p>Spark</p>"}}}},
    })
    jobs = fetch_smartrecruiters(http, Employer("Acme", "smartrecruiters", "acme"), [])
    assert [j.location for j in jobs] == ["Cologne, de", "Bonn, Germany"]
    enrich_smartrecruiters(http, jobs[0])
    assert "Spark" in jobs[0].description and "detail_url" not in jobs[0].extra


def test_personio_xml():
    xml = """<?xml version="1.0"?><workzag-jobs><position><id>987654</id><office>Hamburg</office>
      <additionalOffices><office>Remote</office></additionalOffices><name>Data Platform Engineer</name>
      <createdAt>2026-11-15T08:00:00+00:00</createdAt><jobDescriptions><jobDescription><name>Your tasks</name>
      <value><![CDATA[<p>Kafka and dbt</p>]]></value></jobDescription></jobDescriptions></position></workzag-jobs>"""
    http = FakeHttp({"https://acme.jobs.personio.de/xml": xml})
    [job] = fetch_personio(http, Employer("Acme", "personio", "acme"), [])
    assert job.url == "https://acme.jobs.personio.de/job/987654"
    assert job.location == "Hamburg, Remote" and "Kafka and dbt" in job.description


def test_recruitee_only_published():
    http = FakeHttp({"https://acme.recruitee.com/api/offers/": {"offers": [
        {"title": "Data Engineer", "careers_url": "https://acme.recruitee.com/o/data-engineer", "status": "published",
         "location": "Amsterdam", "published_at": "2026-11-20 10:00:00 UTC", "description": "<p>a</p>", "requirements": "<p>b</p>"},
        {"title": "Old", "careers_url": "https://acme.recruitee.com/o/old", "status": "closed"},
    ]}})
    jobs = fetch_recruitee(http, Employer("Acme", "recruitee", "acme"), [])
    assert len(jobs) == 1 and jobs[0].posted == date(2026, 11, 20)


def test_workday_search_dedupe_and_detail():
    def jobs_route(url, body):
        return {"jobPostings": [{"title": f"Data Engineer {body['searchText']}", "externalPath": "/job/Berlin/Data-Engineer_R1234",
                                 "locationsText": "Berlin", "postedOn": "Posted 3 Days Ago"}]}
    http = FakeHttp({
        "https://acme.wd3.myworkdayjobs.com/wday/cxs/acme/External/jobs": jobs_route,
        "https://acme.wd3.myworkdayjobs.com/wday/cxs/acme/External/job/": {"jobPostingInfo": {
            "jobDescription": "<p>Databricks</p>", "startDate": "2026-11-20", "canApply": True}},
    })
    emp = Employer("Acme", "workday", board_url="https://acme.wd3.myworkdayjobs.com/en-US/External")
    jobs = fetch_workday(http, emp, ["Data Engineer", "ML Engineer"])
    assert len(jobs) == 1
    assert jobs[0].url == "https://acme.wd3.myworkdayjobs.com/External/job/Berlin/Data-Engineer_R1234"
    enrich_workday(http, jobs[0])
    assert "Databricks" in jobs[0].description and jobs[0].posted == date(2026, 11, 20)


def test_workday_helpers():
    assert workday_parts("https://acme.wd3.myworkdayjobs.com/en-US/Careers/") == ("acme.wd3.myworkdayjobs.com", "acme", "Careers")
    today = date(2026, 11, 25)
    assert workday_posted("Posted Today", today) == today
    assert workday_posted("Posted Yesterday", today) == date(2026, 11, 24)
    assert workday_posted("Posted 30+ Days Ago", today) == date(2026, 10, 26)


def test_arbeitsagentur_dedupes_across_queries():
    item = {"refnr": "10000-1234567890-S", "titel": "Data Engineer (m/w/d)", "arbeitgeber": "Muster GmbH",
            "arbeitsort": {"ort": "Köln", "region": "Nordrhein-Westfalen", "land": "Deutschland"},
            "aktuelleVeroeffentlichungsdatum": "2026-11-22", "externeUrl": "https://muster.de/jobs/1"}
    http = FakeHttp({"https://rest.arbeitsagentur.de/": {"stellenangebote": [item]}})
    jobs = fetch_arbeitsagentur(http, ArbeitsagenturConfig(True, "Köln", 30), ["Data Engineer", "Dateningenieur"], 21)
    assert len(jobs) == 1
    assert jobs[0].url.endswith("/jobdetail/10000-1234567890-S")
    assert jobs[0].external_url == "https://muster.de/jobs/1"
    assert "umkreis=30" in http.calls[0][1]
