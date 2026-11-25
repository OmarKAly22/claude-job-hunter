"""Load and validate the engine's TOML configuration."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUPPORTED_ATS = ("greenhouse", "lever", "ashby", "smartrecruiters", "personio", "recruitee", "workday")
DEFAULT_CONFIG = Path("~/JobHunter/config.toml")


class ConfigError(ValueError):
    pass


@dataclass
class Employer:
    name: str
    ats: str
    slug: str = ""
    board_url: str = ""
    region: str = ""
    domain: str = ""


@dataclass
class SearchConfig:
    titles: list[str] = field(default_factory=list)
    extra_keywords: list[str] = field(default_factory=list)
    exclude_title_words: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    exclude_locations: list[str] = field(default_factory=list)
    exclude_employers: list[str] = field(default_factory=list)
    max_age_days: int = 21
    max_new_per_run: int = 60


@dataclass
class VerifyConfig:
    browser: bool = True
    timeout_seconds: int = 25


@dataclass
class ArbeitsagenturConfig:
    enabled: bool = False
    where: str = ""
    radius_km: int = 50


@dataclass
class InboxConfig:
    enabled: bool = False
    host: str = ""
    port: int = 993
    user: str = ""
    folder: str = "INBOX"
    days: int = 8
    password_env: str = "JOB_HUNTER_IMAP_PASSWORD"


@dataclass
class NotifyConfig:
    desktop: bool = True
    email_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    password_env: str = "JOB_HUNTER_SMTP_PASSWORD"


@dataclass
class Config:
    path: Path
    output_folder: Path
    search: SearchConfig
    verify: VerifyConfig
    employers: list[Employer]
    arbeitsagentur: ArbeitsagenturConfig
    inbox: InboxConfig
    notify: NotifyConfig


def _section(data: dict[str, Any], name: str, cls: type) -> Any:
    raw = data.get(name, {}) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"[{name}] must be a table")
    known = set(cls.__dataclass_fields__)
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"unknown keys in [{name}]: {', '.join(sorted(unknown))}")
    return cls(**raw)


def resolve_config_path(path: str | os.PathLike[str] | None) -> Path:
    if path:
        return Path(path).expanduser()
    env = os.environ.get("JOB_HUNTER_CONFIG")
    return Path(env).expanduser() if env else DEFAULT_CONFIG.expanduser()


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    cfg_path = resolve_config_path(path)
    if not cfg_path.exists():
        raise ConfigError(f"config file not found: {cfg_path}. Create one with: job-hunter init")
    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{cfg_path}: {exc}") from exc

    output = data.get("output", {}) or {}
    folder = Path(str(output.get("folder", "~/JobHunter"))).expanduser()
    if not folder.is_absolute():
        folder = (cfg_path.parent / folder).resolve()

    employers: list[Employer] = []
    for i, raw in enumerate(data.get("employers", []) or []):
        try:
            emp = Employer(**raw)
        except TypeError as exc:
            raise ConfigError(f"[[employers]] #{i + 1}: {exc}") from exc
        emp.ats = emp.ats.lower().strip()
        if emp.ats not in SUPPORTED_ATS:
            raise ConfigError(f"[[employers]] {emp.name}: ats must be one of {', '.join(SUPPORTED_ATS)}")
        if emp.ats == "workday" and not emp.board_url:
            raise ConfigError(f"[[employers]] {emp.name}: workday needs board_url")
        if emp.ats != "workday" and not emp.slug:
            raise ConfigError(f"[[employers]] {emp.name}: {emp.ats} needs slug")
        employers.append(emp)

    search = _section(data, "search", SearchConfig)
    if not search.titles and not search.extra_keywords:
        raise ConfigError("[search] needs at least one entry in titles or extra_keywords")

    return Config(
        path=cfg_path,
        output_folder=folder,
        search=search,
        verify=_section(data, "verify", VerifyConfig),
        employers=employers,
        arbeitsagentur=_section(data, "arbeitsagentur", ArbeitsagenturConfig),
        inbox=_section(data, "inbox", InboxConfig),
        notify=_section(data, "notify", NotifyConfig),
    )


def example_config_text() -> str:
    return (Path(__file__).parent / "config.example.toml").read_text(encoding="utf-8")


def get_secret(env_name: str, keyring_name: str) -> str | None:
    """Read a password from an environment variable, then from the OS keychain (if keyring is installed)."""
    value = os.environ.get(env_name)
    if value:
        return value
    try:
        import keyring  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return keyring.get_password("job-hunter", keyring_name)
    except Exception:  # keyring backends raise many different errors
        return None
