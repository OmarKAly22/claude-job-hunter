from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any


@dataclass
class Job:
    company: str
    title: str
    url: str
    location: str
    source: str  # e.g. "greenhouse:example" or "arbeitsagentur"
    posted: date | None = None
    description: str = ""
    remote: bool | None = None
    external_url: str = ""  # e.g. the employer's own posting behind a job-board entry
    # Filled during verification
    status: str = "unchecked"  # live | dead | unverifiable
    verification: str = ""  # browser | ats-api
    link_proof: str = ""
    link_checked: str = ""
    reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_description: bool = True) -> dict[str, Any]:
        data = asdict(self)
        data["posted"] = self.posted.isoformat() if self.posted else None
        if not include_description:
            data.pop("description", None)
        if not self.extra:
            data.pop("extra", None)
        return data


def parse_date(value: Any) -> date | None:
    """Parse the date formats the job APIs use: ISO strings, epoch milliseconds, 'YYYY-MM-DD HH:MM:SS UTC'."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date()
    text = str(value).strip().replace(" UTC", "+00:00")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
