"""Job sources: public job-board APIs of applicant tracking systems, and the Bundesagentur für Arbeit.

Each fetcher returns every open job on the board (or for the search), not filtered.
A job that appears in the employer's own live ATS listing in this run is itself evidence that it is open.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Callable
from urllib.parse import quote, urlparse

from .config import ArbeitsagenturConfig, Employer
from .models import Job, parse_date
from .net import Http, html_to_text


def fetch_greenhouse(http: Http, emp: Employer, titles: list[str]) -> list[Job]:
    data = http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{quote(emp.slug)}/jobs?content=true")
    jobs = []
    for j in data.get("jobs", []):
        jobs.append(Job(
            company=emp.name,
            title=j.get("title", "").strip(),
            url=j.get("absolute_url", ""),
            location=(j.get("location") or {}).get("name", ""),
            source=f"greenhouse:{emp.slug}",
            posted=parse_date(j.get("first_published") or j.get("updated_at")),
            description=html_to_text(j.get("content")),
        ))
    return jobs


def fetch_lever(http: Http, emp: Employer, titles: list[str]) -> list[Job]:
    host = "api.eu.lever.co" if emp.region.lower() == "eu" else "api.lever.co"
    data = http.get_json(f"https://{host}/v0/postings/{quote(emp.slug)}?mode=json")
    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        locations = cats.get("allLocations") or [cats.get("location", "")]
        parts = [j.get("descriptionPlain", "")]
        for block in j.get("lists") or []:
            parts.append(block.get("text", ""))
            parts.append(html_to_text(block.get("content", "")))
        parts.append(j.get("additionalPlain", ""))
        jobs.append(Job(
            company=emp.name,
            title=j.get("text", "").strip(),
            url=j.get("hostedUrl", ""),
            location=", ".join(x for x in locations if x),
            source=f"lever:{emp.slug}",
            posted=parse_date(j.get("createdAt")),
            description="\n".join(p for p in parts if p).strip(),
            remote=(j.get("workplaceType") == "remote") if j.get("workplaceType") else None,
        ))
    return jobs


def fetch_ashby(http: Http, emp: Employer, titles: list[str]) -> list[Job]:
    data = http.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{quote(emp.slug)}?includeCompensation=false")
    jobs = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locations = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        jobs.append(Job(
            company=emp.name,
            title=j.get("title", "").strip(),
            url=j.get("jobUrl", ""),
            location=", ".join(x for x in locations if x),
            source=f"ashby:{emp.slug}",
            posted=parse_date(j.get("publishedAt")),
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            remote=j.get("isRemote"),
        ))
    return jobs


def fetch_smartrecruiters(http: Http, emp: Employer, titles: list[str]) -> list[Job]:
    jobs: list[Job] = []
    offset = 0
    while True:
        data = http.get_json(
            f"https://api.smartrecruiters.com/v1/companies/{quote(emp.slug)}/postings?limit=100&offset={offset}")
        content = data.get("content", [])
        for j in content:
            loc = j.get("location") or {}
            place = loc.get("fullLocation") or ", ".join(x for x in (loc.get("city"), loc.get("country")) if x)
            jobs.append(Job(
                company=emp.name,
                title=j.get("name", "").strip(),
                url=f"https://jobs.smartrecruiters.com/{emp.slug}/{j.get('id')}",
                location=place,
                source=f"smartrecruiters:{emp.slug}",
                posted=parse_date(j.get("releasedDate")),
                remote=loc.get("remote"),
                extra={"detail_url": f"https://api.smartrecruiters.com/v1/companies/{quote(emp.slug)}/postings/{j.get('id')}"},
            ))
        offset += len(content)
        if not content or offset >= data.get("totalFound", 0) or offset >= 1000:
            break
    return jobs


def enrich_smartrecruiters(http: Http, job: Job) -> None:
    detail = http.get_json(job.extra.pop("detail_url"))
    sections = (detail.get("jobAd") or {}).get("sections") or {}
    parts = []
    for key in ("jobDescription", "qualifications", "additionalInformation"):
        sec = sections.get(key) or {}
        if sec.get("text"):
            parts.append(f"{sec.get('title', '')}\n{html_to_text(sec['text'])}".strip())
    job.description = "\n\n".join(parts)


def fetch_personio(http: Http, emp: Employer, titles: list[str]) -> list[Job]:
    domain = emp.domain or "jobs.personio.de"
    root = ET.fromstring(http.get_text(f"https://{emp.slug}.{domain}/xml?language=en"))
    jobs = []
    for pos in root.iter("position"):
        offices = [pos.findtext("office", "")] + [o.text or "" for o in pos.iterfind("additionalOffices/office")]
        parts = []
        for jd in pos.iterfind("jobDescriptions/jobDescription"):
            parts.append(f"{jd.findtext('name', '')}\n{html_to_text(jd.findtext('value', ''))}".strip())
        jobs.append(Job(
            company=emp.name,
            title=(pos.findtext("name") or "").strip(),
            url=f"https://{emp.slug}.{domain}/job/{pos.findtext('id')}",
            location=", ".join(o for o in offices if o),
            source=f"personio:{emp.slug}",
            posted=parse_date(pos.findtext("createdAt")),
            description="\n\n".join(parts),
        ))
    return jobs


def fetch_recruitee(http: Http, emp: Employer, titles: list[str]) -> list[Job]:
    data = http.get_json(f"https://{quote(emp.slug)}.recruitee.com/api/offers/")
    jobs = []
    for j in data.get("offers", []):
        if j.get("status") not in (None, "published"):
            continue
        place = j.get("location") or ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        jobs.append(Job(
            company=emp.name,
            title=j.get("title", "").strip(),
            url=j.get("careers_url", ""),
            location=place,
            source=f"recruitee:{emp.slug}",
            posted=parse_date(j.get("published_at")),
            description=(html_to_text(j.get("description")) + "\n\n" + html_to_text(j.get("requirements"))).strip(),
            remote=j.get("remote"),
        ))
    return jobs


_LOCALE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


def workday_parts(board_url: str) -> tuple[str, str, str]:
    """https://acme.wd3.myworkdayjobs.com/en-US/External -> (host, tenant, site)."""
    parsed = urlparse(board_url)
    segments = [s for s in parsed.path.split("/") if s and not _LOCALE.match(s)]
    if not parsed.netloc or not segments:
        raise ValueError(f"cannot read the Workday site from {board_url}")
    return parsed.netloc, parsed.netloc.split(".")[0], segments[0]


def workday_posted(text: str, today: date | None = None) -> date | None:
    today = today or date.today()
    t = (text or "").lower()
    if "today" in t:
        return today
    if "yesterday" in t:
        return today - timedelta(days=1)
    match = re.search(r"(\d+)\+?\s*day", t)
    return today - timedelta(days=int(match.group(1))) if match else None


def fetch_workday(http: Http, emp: Employer, titles: list[str]) -> list[Job]:
    host, tenant, site = workday_parts(emp.board_url)
    api = f"https://{host}/wday/cxs/{tenant}/{site}"
    seen: dict[str, Job] = {}
    for query in titles or [""]:
        for offset in (0, 20):
            data = http.post_json(f"{api}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": query})
            postings = data.get("jobPostings", [])
            for j in postings:
                path = j.get("externalPath", "")
                if not path or path in seen:
                    continue
                seen[path] = Job(
                    company=emp.name,
                    title=j.get("title", "").strip(),
                    url=f"https://{host}/{site}{path}",
                    location=j.get("locationsText", ""),
                    source=f"workday:{tenant}",
                    posted=workday_posted(j.get("postedOn", "")),
                    extra={"detail_url": f"{api}{path}"},
                )
            if len(postings) < 20:
                break
    return list(seen.values())


def enrich_workday(http: Http, job: Job) -> None:
    info = http.get_json(job.extra.pop("detail_url")).get("jobPostingInfo") or {}
    job.description = html_to_text(info.get("jobDescription"))
    job.posted = parse_date(info.get("startDate")) or job.posted
    if info.get("canApply") is False:
        job.extra["closed_hint"] = "Workday says applications are closed"


FETCHERS: dict[str, Callable[[Http, Employer, list[str]], list[Job]]] = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "personio": fetch_personio,
    "recruitee": fetch_recruitee,
    "workday": fetch_workday,
}

ENRICHERS: dict[str, Callable[[Http, Job], None]] = {
    "smartrecruiters": enrich_smartrecruiters,
    "workday": enrich_workday,
}

ARBEITSAGENTUR_API = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
ARBEITSAGENTUR_KEY = {"X-API-Key": "jobboerse-jobsuche"}  # the public key the official web app uses


def fetch_arbeitsagentur(http: Http, cfg: ArbeitsagenturConfig, titles: list[str], max_age_days: int) -> list[Job]:
    jobs: dict[str, Job] = {}
    for query in titles:
        params = f"was={quote(query)}&angebotsart=1&size=50&page=1&veroeffentlichtseit={max_age_days}"
        if cfg.where:
            params += f"&wo={quote(cfg.where)}&umkreis={cfg.radius_km}"
        data = http.get_json(f"{ARBEITSAGENTUR_API}?{params}", headers=ARBEITSAGENTUR_KEY)
        for j in data.get("stellenangebote", []) or []:
            ref = j.get("refnr")
            if not ref or ref in jobs:
                continue
            place = j.get("arbeitsort") or {}
            jobs[ref] = Job(
                company=j.get("arbeitgeber", "").strip(),
                title=(j.get("titel") or j.get("beruf") or "").strip(),
                url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}",
                location=", ".join(x for x in (place.get("ort"), place.get("region"), place.get("land")) if x),
                source="arbeitsagentur",
                posted=parse_date(j.get("aktuelleVeroeffentlichungsdatum") or j.get("eintrittsdatum")),
                external_url=j.get("externeUrl", "") or "",
            )
    return list(jobs.values())
