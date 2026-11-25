"""Read job emails over IMAP, read-only. The mailbox is opened with EXAMINE (read-only) and messages are fetched
with BODY.PEEK, so nothing is marked as read, moved, deleted or sent."""
from __future__ import annotations

import email
import imaplib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from email.message import Message
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Iterable

from .config import Config, InboxConfig, get_secret
from .net import html_to_text

ATS_SENDERS = (
    "greenhouse", "lever.co", "ashbyhq", "myworkday", "workday", "workable", "personio", "smartrecruiters",
    "teamtailor", "recruitee", "join.com", "successfactors", "icims", "jobvite", "taleo", "softgarden",
    "onlyfy", "rexx", "bite.de", "dvinci", "indeed", "linkedin",
)
CATEGORIES: list[tuple[str, list[str]]] = [
    # Order matters: the first category that matches wins.
    ("interview", ["interview", "vorstellungsgespräch", "kennenlernen", "kennenlerngespräch", "schedule a call",
                   "schedule a conversation", "book a time", "calendly", "goodtime", "next step", "nächste schritt",
                   "invitation to", "einladung"]),
    ("rejection", ["unfortunately", "not moving forward", "other candidates", "decided not to", "will not be moving",
                   "not to proceed", "leider", "absage", "anderen kandidat", "nicht weiter berücksichtigen",
                   "nicht berücksichtigen", "regret to inform"]),
    ("closed", ["position has been filled", "role is closed", "role has been closed", "on hold",
                "stelle wurde besetzt", "stelle ist besetzt", "nicht mehr besetzt"]),
    ("confirmation", ["thank you for applying", "thanks for applying", "application received", "we received your application",
                      "we have received your application", "your application for", "eingangsbestätigung",
                      "ihre bewerbung", "deine bewerbung", "bewerbung erhalten", "vielen dank für ihre bewerbung"]),
    ("job_alert", ["job alert", "jobs for you", "new jobs", "jobagent", "job-agent", "passende jobs", "neue jobs",
                   "recommended jobs", "jobs you may be interested in"]),
]


@dataclass
class JobEmail:
    date: str
    sender: str
    sender_name: str
    subject: str
    category: str
    snippet: str
    message_id: str


def _body_text(msg: Message) -> str:
    plain, html = "", ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ctype = part.get_content_type()
        try:
            payload = part.get_content()  # type: ignore[attr-defined]
        except Exception:
            raw = part.get_payload(decode=True) or b""
            payload = raw.decode(part.get_content_charset() or "utf-8", "replace")
        if ctype == "text/plain" and not plain:
            plain = str(payload)
        elif ctype == "text/html" and not html:
            html = str(payload)
    text = plain or html_to_text(html)
    return re.sub(r"\s+", " ", text).strip()


def classify(subject: str, body: str, sender: str) -> str | None:
    """Return the category of a job email, or None when it is not about a job application."""
    hay = f"{subject}\n{body[:3000]}".lower()
    for name, words in CATEGORIES:
        if any(w in hay for w in words):
            if name in ("interview", "rejection") and not _job_context(hay, sender):
                continue  # "unfortunately" or "next steps" in a non-job email
            return name
    return "other_ats" if any(s in sender.lower() for s in ATS_SENDERS) else None


def _job_context(hay: str, sender: str) -> bool:
    words = ("application", "applying", "bewerbung", "position", "role", "stelle", "candidate", "kandidat",
             "recruit", "hiring", "vacancy", "talent")
    return any(w in hay for w in words) or any(s in sender.lower() for s in ATS_SENDERS)


def parse_message(raw: bytes) -> JobEmail | None:
    msg = email.message_from_bytes(raw, policy=default_policy)
    subject = str(msg.get("Subject", "")).strip()
    name, addr = parseaddr(str(msg.get("From", "")))
    body = _body_text(msg)
    category = classify(subject, body, addr)
    if not category:
        return None
    try:
        when = parsedate_to_datetime(str(msg.get("Date"))).date().isoformat()
    except (TypeError, ValueError):
        when = ""
    return JobEmail(when, addr, name, subject, category, body[:1500], str(msg.get("Message-ID", "")))


def parse_eml_files(paths: Iterable[Path]) -> list[JobEmail]:
    out = []
    for path in paths:
        item = parse_message(Path(path).read_bytes())
        if item:
            out.append(item)
    return out


def fetch_imap(cfg: InboxConfig, days: int | None = None) -> list[JobEmail]:
    password = get_secret(cfg.password_env, "inbox")
    if not password:
        raise RuntimeError(f"no IMAP password: set {cfg.password_env} or run 'job-hunter set-password inbox'")
    since = (date.today() - timedelta(days=days or cfg.days)).strftime("%d-%b-%Y")
    out: list[JobEmail] = []
    with imaplib.IMAP4_SSL(cfg.host, cfg.port) as imap:
        imap.login(cfg.user, password)
        status, _ = imap.select(_quote(cfg.folder), readonly=True)
        if status != "OK":
            raise RuntimeError(f"cannot open mailbox folder {cfg.folder}")
        status, data = imap.search(None, "SINCE", since)
        if status != "OK":
            raise RuntimeError("IMAP search failed")
        for num in (data[0] or b"").split():
            status, parts = imap.fetch(num, "(BODY.PEEK[])")
            if status != "OK":
                continue
            for part in parts:
                if isinstance(part, tuple):
                    item = parse_message(part[1])
                    if item:
                        out.append(item)
    out.sort(key=lambda e: e.date, reverse=True)
    return out


def _quote(folder: str) -> str:
    return folder if folder.startswith('"') else f'"{folder}"'


def export_inbox(cfg: Config, emails: list[JobEmail], now: datetime | None = None) -> Path:
    now = now or datetime.now()
    folder = cfg.output_folder / "inbox"
    folder.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for e in emails:
        counts[e.category] = counts.get(e.category, 0) + 1
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "mailbox": f"{cfg.inbox.user} / {cfg.inbox.folder}",
        "days": cfg.inbox.days,
        "counts": counts,
        "emails": [asdict(e) for e in emails],
    }
    text = json.dumps(payload, indent=1, ensure_ascii=False)
    path = folder / f"inbox-{now:%Y-%m-%dT%H%M}.json"
    path.write_text(text, encoding="utf-8")
    (cfg.output_folder / "latest-inbox.json").write_text(text, encoding="utf-8")
    return path
