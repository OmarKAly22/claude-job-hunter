from datetime import date

from job_hunter_engine.config import SearchConfig
from job_hunter_engine.filters import scope_reason, title_matches
from job_hunter_engine.models import Job
from job_hunter_engine.verify import assess_page

CFG = SearchConfig(
    titles=["Data Engineer", "Machine Learning Engineer"], extra_keywords=["MLOps"],
    exclude_title_words=["junior", "werkstudent"], locations=["Germany", "Deutschland", "Remote", "Berlin"],
    exclude_employers=["Old Employer"], max_age_days=21,
)


def job(**kw):
    base = dict(company="Acme", title="Senior Data Engineer", url="https://x/1", location="Berlin", source="t")
    base.update(kw)
    return Job(**base)


def test_title_matching():
    assert title_matches("Senior Data Engineer (m/w/d)", CFG)
    assert title_matches("Engineer, Data Platform – Data", CFG)  # word order ignored
    assert title_matches("Lead MLOps Specialist", CFG)
    assert not title_matches("Junior Data Engineer", CFG)
    assert not title_matches("Werkstudent Data Engineering", CFG)
    assert not title_matches("Data Analyst", CFG)


def test_scope_reasons():
    today = date(2026, 11, 25)
    assert scope_reason(job(), CFG, today) is None
    assert scope_reason(job(company="Old Employer GmbH"), CFG, today) == "Excluded employer"
    assert scope_reason(job(location="Paris, France"), CFG, today) == "Location: Paris, France"
    assert scope_reason(job(location="Paris", remote=True), CFG, today) is None
    assert scope_reason(job(location=""), CFG, today) is None
    assert scope_reason(job(posted=date(2026, 10, 1)), CFG, today) == "Stale"


LONG = "Senior Data Engineer. " + "We build data platforms with Python and Spark. " * 20


def test_live_page():
    res = assess_page("https://boards.greenhouse.io/acme/jobs/4012345", "https://boards.greenhouse.io/acme/jobs/4012345",
                      200, "Job Application for Senior Data Engineer at Acme", LONG, "Senior Data Engineer (m/w/d)")
    assert res.status == "live" and "Senior Data Engineer" in res.proof


def test_dead_pages():
    url = "https://boards.greenhouse.io/acme/jobs/4012345"
    assert assess_page(url, url, 404, "", "", "Data Engineer").status == "dead"
    assert assess_page(url, "https://boards.greenhouse.io/acme?error=true", 200, "Acme", LONG, "Data Engineer").status == "dead"
    redirected = assess_page(url, "https://boards.greenhouse.io/acme/jobs/4099999", 200, "Other job", LONG, "Senior Data Engineer")
    assert redirected.status == "dead" and "Redirected" in redirected.proof
    to_list = assess_page("https://acme.com/careers/data-engineer-berlin", "https://acme.com/careers", 200, "Careers", LONG, "Data Engineer")
    assert to_list.status == "dead"
    closed = assess_page(url, url, 200, "Senior Data Engineer", "This job is no longer available. " + LONG, "Senior Data Engineer")
    assert closed.status == "dead" and "Closed sign" in closed.proof
    german = assess_page(url, url, 200, "Data Engineer", "Diese Stelle ist leider nicht mehr verfügbar. " + LONG, "Data Engineer")
    assert german.status == "dead"


def test_unverifiable_pages():
    url = "https://jobs.ashbyhq.com/acme/abc"
    assert assess_page(url, url, 200, "Acme", "Loading…", "Data Engineer").status == "unverifiable"
    assert assess_page(url, url, 200, "Acme Careers", "Welcome to Acme. " * 40, "Data Engineer").status == "unverifiable"
    assert assess_page(url, url, 503, "", "", "Data Engineer").status == "unverifiable"
