"""Scope filters applied before any link is opened. Scoring the fit is Claude's job, not the engine's."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from .config import SearchConfig
from .models import Job

# Gender and form suffixes common in German postings: (m/w/d), (f/m/x), (all genders), (w/m/div.)
_SUFFIX = re.compile(r"\((?:[mwfdx]\s*/\s*){1,3}[mwfdx](?:iv\.?)?\)|\(all genders?\)|\(gn\)|\*in\b|:in\b", re.I)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = _SUFFIX.sub(" ", text)
    text = re.sub(r"[^\w+#]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> set[str]:
    return set(normalize(text).split())


def title_matches(title: str, cfg: SearchConfig) -> bool:
    words = tokens(title)
    norm = f" {normalize(title)} "
    for bad in cfg.exclude_title_words:
        if f" {normalize(bad)} " in norm:
            return False
    for wanted in cfg.titles:
        want = tokens(wanted)
        if want and want <= words:
            return True
    return any(f" {normalize(k)} " in norm for k in cfg.extra_keywords if k.strip())


def location_matches(job: Job, cfg: SearchConfig) -> bool:
    place = normalize(job.location)
    if job.remote:
        place += " remote"
    padded = f" {place} "
    if any(f" {normalize(x)} " in padded for x in cfg.exclude_locations if x.strip()):
        return False
    if not cfg.locations:
        return True
    if not place:
        return True  # unknown location: let the browser check and Claude decide
    return any(f" {normalize(x)} " in padded for x in cfg.locations if x.strip())


def employer_excluded(company: str, cfg: SearchConfig) -> bool:
    name = f" {normalize(company)} "
    return any(f" {normalize(x)} " in name for x in cfg.exclude_employers if x.strip())


def too_old(job: Job, cfg: SearchConfig, today: date | None = None) -> bool:
    if not job.posted or not cfg.max_age_days:
        return False
    return ((today or date.today()) - job.posted).days > cfg.max_age_days


def scope_reason(job: Job, cfg: SearchConfig, today: date | None = None) -> str | None:
    """None when the job is in scope, otherwise the reason it was dropped (same wording as seen.csv)."""
    if employer_excluded(job.company, cfg):
        return "Excluded employer"
    if not title_matches(job.title, cfg):
        return "Title not in profile"
    if not location_matches(job, cfg):
        return f"Location: {job.location or 'unknown'}"
    if too_old(job, cfg, today):
        return "Stale"
    return None
