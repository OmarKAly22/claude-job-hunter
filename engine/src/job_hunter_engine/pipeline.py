"""One search run: fetch every source, filter to scope, skip what was seen before, check links, export JSON."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .config import Config
from .filters import normalize, scope_reason
from .models import Job
from .net import Http, HttpError
from .sources import ENRICHERS, FETCHERS, fetch_arbeitsagentur
from .verify import BrowserChecker, HttpChecker, make_checker

log = logging.getLogger("job_hunter")
MAX_DESCRIPTION = 8000
RETRY_UNVERIFIABLE = 3


class State:
    """Remembers every job URL the engine has handed over, so the same job is never exported twice."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {"seen": {}}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                backup = path.with_suffix(".broken.json")
                path.replace(backup)
                log.warning("state file was unreadable; moved to %s and started fresh", backup)
        self.data.setdefault("seen", {})

    def key(self, job: Job) -> str:
        return job.url.split("#")[0].rstrip("/")

    def company_title_key(self, job: Job) -> str:
        return f"{normalize(job.company)}|{normalize(job.title)}"

    def is_done(self, job: Job) -> bool:
        entry = self.data["seen"].get(self.key(job))
        if entry is None:
            entry = self.data.get("by_title", {}).get(self.company_title_key(job))
        if entry is None:
            return False
        return not (entry.get("status") == "unverifiable" and entry.get("attempts", 1) < RETRY_UNVERIFIABLE)

    def record(self, job: Job, today: str) -> None:
        key = self.key(job)
        old = self.data["seen"].get(key, {})
        entry = {
            "first_seen": old.get("first_seen", today),
            "last_checked": today,
            "status": job.status,
            "reason": job.reason,
            "attempts": old.get("attempts", 0) + 1,
        }
        self.data["seen"][key] = entry
        if job.status != "unverifiable":
            self.data.setdefault("by_title", {})[self.company_title_key(job)] = {"status": job.status}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


@dataclass
class SourceReport:
    source: str
    ok: bool = True
    error: str = ""
    found: int = 0
    in_scope: int = 0
    new: int = 0
    live: int = 0
    dead: int = 0
    unverifiable: int = 0


@dataclass
class RunResult:
    export_path: Path | None
    live: list[Job] = field(default_factory=list)
    rejected: list[Job] = field(default_factory=list)
    reports: list[SourceReport] = field(default_factory=list)
    check_method: str = ""
    stopped_early: bool = False

    def summary(self) -> str:
        failed = [r.source for r in self.reports if not r.ok]
        text = f"{len(self.live)} new live jobs from {len(self.reports)} sources"
        if failed:
            text += f"; {len(failed)} source(s) failed: {', '.join(failed[:5])}"
        return text


def _verify_job(job: Job, checker: HttpChecker | BrowserChecker, listed_by_api: bool, today: str) -> None:
    job.link_checked = today
    if job.extra.pop("closed_hint", None):
        job.status, job.reason = "dead", "Dead link: the ATS says applications are closed"
        return
    check = checker.check(job.url, job.title)
    if check.status == "live":
        job.status, job.verification, job.link_proof = "live", checker.method, check.proof
        if not job.description and check.text:
            job.description = check.text
    elif check.status == "dead":
        job.status, job.reason = "dead", f"Dead link: {check.proof}"
    elif listed_by_api:
        # The page could not be read, but the employer's live ATS listing returned this job in this run.
        job.status, job.verification = "live", "ats-api"
        job.link_proof = f"Listed in {job.source} API on {today} (page not readable: {check.proof})"
    else:
        job.status, job.reason = "unverifiable", f"Link not verifiable: {check.proof}"
    job.description = job.description[:MAX_DESCRIPTION]


def run_search(cfg: Config, *, http: Http | None = None, checker: HttpChecker | BrowserChecker | None = None,
               today: date | None = None, max_new: int | None = None,
               progress: Callable[[str], None] | None = None) -> RunResult:
    say = progress or (lambda msg: log.info(msg))
    http = http or Http(timeout=cfg.verify.timeout_seconds)
    today_d = today or date.today()
    today_s = today_d.isoformat()
    limit = max_new or cfg.search.max_new_per_run
    cfg.output_folder.mkdir(parents=True, exist_ok=True)
    state = State(cfg.output_folder / "state.json")

    candidates: list[tuple[Job, SourceReport, bool]] = []
    reports: list[SourceReport] = []
    rejected: list[Job] = []

    def take(jobs: list[Job], report: SourceReport, listed_by_api: bool) -> None:
        report.found = len(jobs)
        for job in jobs:
            if not job.url:
                continue
            reason = scope_reason(job, cfg.search, today_d)
            if reason:
                continue  # out of scope: not recorded, so a profile change can bring it back
            report.in_scope += 1
            if state.is_done(job):
                continue
            report.new += 1
            candidates.append((job, report, listed_by_api))

    for emp in cfg.employers:
        report = SourceReport(f"{emp.ats}:{emp.name}")
        reports.append(report)
        try:
            say(f"Fetching {emp.name} ({emp.ats})")
            take(FETCHERS[emp.ats](http, emp, cfg.search.titles), report, True)
        except (HttpError, ValueError, KeyError, TypeError) as exc:
            report.ok, report.error = False, str(exc)[:300]
            log.warning("%s failed: %s", report.source, exc)

    if cfg.arbeitsagentur.enabled:
        report = SourceReport("arbeitsagentur")
        reports.append(report)
        try:
            say("Searching Bundesagentur für Arbeit")
            take(fetch_arbeitsagentur(http, cfg.arbeitsagentur, cfg.search.titles, cfg.search.max_age_days),
                 report, True)
        except (HttpError, ValueError, KeyError, TypeError) as exc:
            report.ok, report.error = False, str(exc)[:300]
            log.warning("arbeitsagentur failed: %s", exc)

    # Newest first, so a run that stops at the limit keeps the freshest jobs.
    candidates.sort(key=lambda c: c[0].posted or date.min, reverse=True)

    own_checker = checker is None
    method_note = ""
    if own_checker:
        checker, method_note = make_checker(cfg.verify.browser, http, cfg.verify.timeout_seconds)
    assert checker is not None
    live: list[Job] = []
    stopped = False
    try:
        for i, (job, report, listed) in enumerate(candidates, 1):
            if len(live) >= limit:
                stopped = True
                break
            source_kind = job.source.split(":")[0]
            if not job.description and source_kind in ENRICHERS:
                try:
                    ENRICHERS[source_kind](http, job)
                except (HttpError, ValueError, KeyError) as exc:
                    log.info("could not load details for %s: %s", job.url, exc)
            say(f"Checking {i}/{len(candidates)}: {job.company} – {job.title}")
            _verify_job(job, checker, listed, today_s)
            setattr(report, job.status, getattr(report, job.status) + 1)
            state.record(job, today_s)
            (live if job.status == "live" else rejected).append(job)
    finally:
        if own_checker:
            checker.close()
        state.save()

    result = RunResult(None, live, rejected, reports, method_note or checker.method, stopped)
    result.export_path = export(cfg, result, datetime.now())
    return result


def export(cfg: Config, result: RunResult, now: datetime) -> Path:
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "engine_version": __version__,
        "check_method": result.check_method,
        "stopped_at_limit": result.stopped_early,
        "summary": result.summary(),
        "sources": [r.__dict__ for r in result.reports],
        "jobs": [j.to_dict() for j in result.live],
        "not_saved": [
            {"company": j.company, "title": j.title, "url": j.url, "source": j.source, "reason": j.reason}
            for j in result.rejected
        ],
    }
    folder = cfg.output_folder / "leads"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"leads-{now:%Y-%m-%dT%H%M}.json"
    text = json.dumps(payload, indent=1, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    (cfg.output_folder / "latest-leads.json").write_text(text, encoding="utf-8")
    return path


def latest_leads(cfg: Config) -> dict[str, Any] | None:
    path = cfg.output_folder / "latest-leads.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def verify_urls(cfg: Config, urls: list[str], titles: list[str] | None = None,
                checker: HttpChecker | BrowserChecker | None = None) -> list[dict[str, str]]:
    """Recheck links (for leads saved on earlier days, or a link the user pasted)."""
    titles = titles or [""] * len(urls)
    own = checker is None
    if own:
        checker, _ = make_checker(cfg.verify.browser, Http(timeout=cfg.verify.timeout_seconds), cfg.verify.timeout_seconds)
    assert checker is not None
    out = []
    try:
        for url, title in zip(urls, titles + [""] * (len(urls) - len(titles))):
            res = checker.check(url, title)
            out.append({"url": url, "status": res.status, "proof": res.proof, "final_url": res.final_url,
                        "method": checker.method, "checked": date.today().isoformat()})
    finally:
        if own:
            checker.close()
    return out
