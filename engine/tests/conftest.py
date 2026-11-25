from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from job_hunter_engine.net import HttpError, Response
from job_hunter_engine.verify import PageCheck


class FakeHttp:
    """Serves canned responses by URL prefix; unknown URLs raise like a 404."""

    def __init__(self, routes: dict[str, Any]):
        self.routes = routes
        self.calls: list[tuple[str, str, Any]] = []

    def _find(self, url: str) -> Any:
        for prefix in sorted(self.routes, key=len, reverse=True):
            if url.startswith(prefix):
                return self.routes[prefix]
        raise HttpError(url, 404, "not found")

    def request(self, url, *, method="GET", headers=None, body=None, allow_error=False):
        self.calls.append((method, url, body))
        value = self._find(url)
        if callable(value):
            value = value(url, body)
        if isinstance(value, Response):
            return value
        return Response(url, 200, value if isinstance(value, str) else json.dumps(value))

    def get_json(self, url, headers=None):
        return self.request(url, headers=headers).json()

    def post_json(self, url, body, headers=None):
        return self.request(url, method="POST", body=body, headers=headers).json()

    def get_text(self, url, headers=None):
        return self.request(url, headers=headers).text


class FakeChecker:
    method = "browser"

    def __init__(self, outcomes: dict[str, PageCheck] | None = None):
        self.outcomes = outcomes or {}
        self.checked: list[str] = []

    def check(self, url, expected_title):
        self.checked.append(url)
        return self.outcomes.get(url, PageCheck("live", expected_title, url, "Job text " * 50))

    def close(self):
        pass


@pytest.fixture
def write_config(tmp_path: Path):
    def _write(body: str) -> Path:
        path = tmp_path / "config.toml"
        path.write_text(f'[output]\nfolder = "{(tmp_path / "out").as_posix()}"\n' + body, encoding="utf-8")
        return path

    return _write


FIXTURES = Path(__file__).parent / "fixtures"
