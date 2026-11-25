"""Link checks. A job counts as live only when its page was opened in this run and showed that single job.

`assess_page` holds the rules and is pure (easy to test). `BrowserChecker` opens pages in headless Chromium
(Playwright). `HttpChecker` is the fallback without a browser: it cannot read pages built by JavaScript, so on
its own it rarely proves a job is live; the employer's live ATS listing is then the proof.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .filters import normalize, tokens
from .net import Http, HttpError, html_title, html_to_text

CLOSED_SIGNS = [
    "job not found", "page not found", "no longer available", "no longer accepting applications",
    "position has been filled", "this position is closed", "this job is closed", "job has expired",
    "posting has expired", "job is no longer", "vacancy has been filled", "no longer open",
    "job has been archived", "posting has been archived",
    "nicht mehr verfügbar", "bereits vergeben", "stelle ist besetzt", "nicht mehr aktiv",
    "stellenanzeige ist abgelaufen", "die stelle wurde bereits", "leider ist diese stelle",
]
LIST_PAGE_PATHS = re.compile(r"/(jobs|careers|karriere|stellenangebote|search|positions|openings)/?$", re.I)
_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\d{5,}|R\d{4,}|[A-Z]{1,4}\d{4,}", re.I)


@dataclass
class PageCheck:
    status: str  # live | dead | unverifiable
    proof: str  # page title when live, otherwise the reason
    final_url: str = ""
    text: str = ""


def _ids(url: str) -> set[str]:
    parsed = urlparse(url)
    return {m.group(0).lower() for m in _ID.finditer(parsed.path + "?" + parsed.query)}


def title_on_page(expected: str, page_title: str, text: str) -> bool:
    want = tokens(expected)
    if not want:
        return True
    haystack = tokens(page_title) | tokens(text[:6000])
    return len(want & haystack) / len(want) >= 0.8


def assess_page(requested_url: str, final_url: str, http_status: int | None, page_title: str, text: str,
                expected_title: str) -> PageCheck:
    final_url = final_url or requested_url
    if http_status is not None and http_status >= 400:
        kind = "dead" if http_status in (404, 410) else "unverifiable"
        return PageCheck(kind, f"HTTP {http_status}", final_url)
    if "error=true" in final_url:
        return PageCheck("dead", "Redirected to an error page", final_url)
    missing = _ids(requested_url) - _ids(final_url)
    if missing and urlparse(final_url).path != urlparse(requested_url).path:
        return PageCheck("dead", "Redirected away from the job", final_url)
    if LIST_PAGE_PATHS.search(urlparse(final_url).path) and not LIST_PAGE_PATHS.search(urlparse(requested_url).path):
        return PageCheck("dead", "Redirected to a job list", final_url)
    head = normalize(f"{page_title} {text[:4000]}")
    for sign in CLOSED_SIGNS:
        if normalize(sign) in head:
            return PageCheck("dead", f"Closed sign: '{sign}'", final_url)
    if len(text.strip()) < 200:
        return PageCheck("unverifiable", "Page had almost no text (built by JavaScript?)", final_url)
    if not title_on_page(expected_title, page_title, text):
        return PageCheck("unverifiable", "Job title not found on the page", final_url)
    proof = page_title.strip() or expected_title
    return PageCheck("live", proof[:200], final_url, text)


class HttpChecker:
    method = "http"

    def __init__(self, http: Http):
        self.http = http

    def check(self, url: str, expected_title: str) -> PageCheck:
        try:
            resp = self.http.request(url, headers={"Accept": "text/html"}, allow_error=True)
        except HttpError as exc:
            return PageCheck("unverifiable", str(exc), url)
        return assess_page(url, resp.url, resp.status, html_title(resp.text), html_to_text(resp.text), expected_title)

    def close(self) -> None:
        pass


class BrowserChecker:
    method = "browser"

    def __init__(self, timeout_seconds: int = 25):
        from playwright.sync_api import sync_playwright  # imported lazily: optional dependency

        self._pw = sync_playwright().start()
        try:
            self._browser, self.browser_name = _launch(self._pw)
        except Exception:
            self._pw.stop()
            raise
        self._context = self._browser.new_context(locale="en-US", viewport={"width": 1280, "height": 900})
        self.timeout_ms = timeout_seconds * 1000

    def check(self, url: str, expected_title: str) -> PageCheck:
        page = self._context.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass  # many job pages keep polling; the DOM is usually ready anyway
            status = response.status if response else None
            text = page.inner_text("body", timeout=5000) if page.query_selector("body") else ""
            return assess_page(url, page.url, status, page.title(), text, expected_title)
        except Exception as exc:  # timeouts, DNS errors, crashed pages
            return PageCheck("unverifiable", f"Browser error: {str(exc).splitlines()[0][:160]}", url)
        finally:
            page.close()

    def close(self) -> None:
        for closer in (self._context.close, self._browser.close, self._pw.stop):
            try:
                closer()
            except Exception:
                pass


def _launch(pw):  # type: ignore[no-untyped-def]
    """Start headless Chromium: Playwright's own build first, then the installed Google Chrome or Microsoft Edge."""
    errors = []
    for channel in (None, "chrome", "msedge"):
        try:
            browser = pw.chromium.launch(headless=True, channel=channel) if channel else pw.chromium.launch(headless=True)
            return browser, channel or "chromium"
        except Exception as exc:
            errors.append(str(exc).splitlines()[0][:100])
    raise RuntimeError("no browser could start: " + " | ".join(errors))


def browser_available() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright is not installed (pip install 'job-hunter-engine[browser]')"
    try:
        with sync_playwright() as pw:
            browser, name = _launch(pw)
            browser.close()
        return True, f"headless {name} ready"
    except Exception:
        return False, "no headless browser: run 'job-hunter setup-browser' (or install Google Chrome)"


def make_checker(use_browser: bool, http: Http, timeout_seconds: int) -> tuple[HttpChecker | BrowserChecker, str]:
    """Return a checker and a note. Falls back to HTTP checks when the browser cannot start."""
    if use_browser:
        try:
            return BrowserChecker(timeout_seconds), "browser"
        except Exception as exc:
            return HttpChecker(http), f"browser unavailable ({str(exc).splitlines()[0][:120]}); used plain HTTP checks"
    return HttpChecker(http), "browser disabled in config; used plain HTTP checks"
