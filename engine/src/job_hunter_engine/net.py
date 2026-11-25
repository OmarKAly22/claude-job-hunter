"""Tiny HTTP helpers on the standard library, so the engine has no required dependencies.

Every source receives an `Http` object, which tests replace with a fake.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any

from . import __version__

USER_AGENT = f"job-hunter-engine/{__version__} (+https://github.com/OmarKAly22/claude-job-hunter)"


class HttpError(RuntimeError):
    def __init__(self, url: str, status: int | None, message: str):
        super().__init__(f"{status or 'error'} for {url}: {message}")
        self.url = url
        self.status = status


@dataclass
class Response:
    url: str  # final URL after redirects
    status: int
    text: str

    def json(self) -> Any:
        return json.loads(self.text)


class Http:
    def __init__(self, timeout: float = 25, min_interval: float = 0.4):
        self.timeout = timeout
        self.min_interval = min_interval
        self._last = 0.0

    def request(self, url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
                body: Any = None, allow_error: bool = False) -> Response:
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        data = None
        hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"}
        if headers:
            hdrs.update(headers)
        if body is not None:
            data = json.dumps(body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return Response(resp.geturl(), resp.status, resp.read().decode(charset, "replace"))
        except urllib.error.HTTPError as exc:
            if allow_error:
                return Response(exc.geturl() or url, exc.code, exc.read().decode("utf-8", "replace"))
            raise HttpError(url, exc.code, exc.reason) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HttpError(url, None, str(getattr(exc, "reason", exc))) from exc
        finally:
            self._last = time.monotonic()

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        return self.request(url, headers=headers).json()

    def post_json(self, url: str, body: Any, headers: dict[str, str] | None = None) -> Any:
        return self.request(url, method="POST", body=body, headers=headers).json()

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        return self.request(url, headers=headers).text


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}
    SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str | None) -> str:
    """Turn HTML (also HTML-escaped HTML, as Greenhouse returns it) into readable plain text."""
    if not html:
        return ""
    if "&lt;" in html and "<" not in html:
        html = unescape(html)
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    return text.strip()


def html_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return unescape(re.sub(r"\s+", " ", match.group(1))).strip() if match else ""
