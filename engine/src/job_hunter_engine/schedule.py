"""Register runs with the computer's own scheduler: launchd (macOS), cron (Linux), Task Scheduler (Windows).

Nothing runs in the background besides what the OS scheduler starts. `job-hunter schedule remove` undoes it all.
"""
from __future__ import annotations

import os
import plistlib
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LABEL = "io.github.omarkaly22.jobhunter"
CRON_MARK = "# job-hunter-engine"
DAYS = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 0}
WIN_DAYS = {"mon": "MON", "tue": "TUE", "wed": "WED", "thu": "THU", "fri": "FRI", "sat": "SAT", "sun": "SUN"}


@dataclass
class Job:
    name: str  # "search" or "inbox"
    hour: int
    minute: int
    days: list[str]  # empty = every day

    def describe(self) -> str:
        when = "every day" if not self.days else ", ".join(d.capitalize() for d in self.days)
        return f"{self.name}: {when} at {self.hour:02d}:{self.minute:02d}"


def parse_when(name: str, time_text: str, days_text: str) -> Job:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", time_text.strip())
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        raise ValueError(f"time must look like 07:30, got {time_text!r}")
    days_text = days_text.strip().lower()
    if days_text in ("", "daily", "every day"):
        days: list[str] = []
    elif days_text == "weekdays":
        days = ["mon", "tue", "wed", "thu", "fri"]
    else:
        days = [d.strip()[:3] for d in days_text.split(",") if d.strip()]
        bad = [d for d in days if d not in DAYS]
        if bad:
            raise ValueError(f"unknown day(s): {', '.join(bad)}; use mon,tue,... or daily or weekdays")
    return Job(name, int(match.group(1)), int(match.group(2)), days)


def command(job: Job, config_path: Path) -> list[str]:
    sub = "run" if job.name == "search" else "inbox"
    return [sys.executable, "-m", "job_hunter_engine", sub, "--config", str(config_path), "--notify"]


# ---------- macOS: launchd ----------

def _plist_path(job: Job) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.{job.name}.plist"


def _launchd_plist(job: Job, config_path: Path, log_dir: Path) -> bytes:
    if job.days:
        interval: list[dict[str, int]] | dict[str, int] = [
            {"Weekday": DAYS[d], "Hour": job.hour, "Minute": job.minute} for d in job.days]
    else:
        interval = {"Hour": job.hour, "Minute": job.minute}
    data = {
        "Label": f"{LABEL}.{job.name}",
        "ProgramArguments": command(job, config_path),
        "StartCalendarInterval": interval,  # launchd runs a missed job when the Mac wakes up
        "StandardOutPath": str(log_dir / f"{job.name}.log"),
        "StandardErrorPath": str(log_dir / f"{job.name}.log"),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }
    return plistlib.dumps(data)


# ---------- Linux: cron ----------

def _cron_line(job: Job, config_path: Path, log_dir: Path) -> str:
    dow = ",".join(str(DAYS[d]) for d in job.days) if job.days else "*"
    cmd = " ".join(shlex.quote(p) for p in command(job, config_path))
    log = shlex.quote(str(log_dir / f"{job.name}.log"))
    return f"{job.minute} {job.hour} * * {dow} {cmd} >> {log} 2>&1 {CRON_MARK}:{job.name}"


def _read_crontab() -> str:
    res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


def _write_crontab(text: str) -> None:
    subprocess.run(["crontab", "-"], input=text, text=True, check=True)


# ---------- Windows: Task Scheduler ----------

def _win_args(job: Job, config_path: Path) -> list[str]:
    cmd = subprocess.list2cmdline(command(job, config_path))
    args = ["schtasks", "/Create", "/F", "/TN", f"JobHunter\\{job.name}", "/TR", cmd,
            "/ST", f"{job.hour:02d}:{job.minute:02d}"]
    if job.days:
        args += ["/SC", "WEEKLY", "/D", ",".join(WIN_DAYS[d] for d in job.days)]
    else:
        args += ["/SC", "DAILY"]
    return args


# ---------- public API ----------

def plan(jobs: list[Job], config_path: Path, log_dir: Path) -> list[str]:
    """Human-readable description of what install() would do on this computer."""
    lines = []
    for job in jobs:
        if sys.platform == "darwin":
            lines.append(f"launchd agent {_plist_path(job)} → {job.describe()}")
        elif sys.platform.startswith("win"):
            lines.append("Task Scheduler: " + subprocess.list2cmdline(_win_args(job, config_path)))
        else:
            lines.append("crontab: " + _cron_line(job, config_path, log_dir))
    return lines


def install(jobs: list[Job], config_path: Path, log_dir: Path) -> list[str]:
    log_dir.mkdir(parents=True, exist_ok=True)
    done = []
    if sys.platform == "darwin":
        uid = os.getuid()
        for job in jobs:
            path = _plist_path(job)
            path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(path)], capture_output=True)
            path.write_bytes(_launchd_plist(job, config_path, log_dir))
            subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(path)], check=True, capture_output=True)
            done.append(f"{job.describe()} (launchd)")
    elif sys.platform.startswith("win"):
        for job in jobs:
            subprocess.run(_win_args(job, config_path), check=True, capture_output=True)
            done.append(f"{job.describe()} (Task Scheduler)")
    else:
        names = {j.name for j in jobs}
        kept = [ln for ln in _read_crontab().splitlines()
                if not any(ln.endswith(f"{CRON_MARK}:{n}") for n in names)]
        kept += [_cron_line(j, config_path, log_dir) for j in jobs]
        _write_crontab("\n".join(kept) + "\n")
        done += [f"{j.describe()} (cron)" for j in jobs]
    return done


def remove() -> list[str]:
    removed = []
    if sys.platform == "darwin":
        uid = os.getuid()
        for name in ("search", "inbox"):
            path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.{name}.plist"
            if path.exists():
                subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(path)], capture_output=True)
                path.unlink()
                removed.append(str(path))
    elif sys.platform.startswith("win"):
        for name in ("search", "inbox"):
            res = subprocess.run(["schtasks", "/Delete", "/F", "/TN", f"JobHunter\\{name}"], capture_output=True)
            if res.returncode == 0:
                removed.append(f"JobHunter\\{name}")
    else:
        lines = _read_crontab().splitlines()
        kept = [ln for ln in lines if CRON_MARK not in ln]
        if len(kept) != len(lines):
            _write_crontab("\n".join(kept) + ("\n" if kept else ""))
            removed.append(f"{len(lines) - len(kept)} crontab line(s)")
    return removed


def show() -> list[str]:
    if sys.platform == "darwin":
        return [str(p) for p in (Path.home() / "Library" / "LaunchAgents").glob(f"{LABEL}.*.plist")]
    if sys.platform.startswith("win"):
        res = subprocess.run(["schtasks", "/Query", "/TN", "JobHunter\\", "/FO", "LIST"], capture_output=True, text=True)
        return [ln for ln in res.stdout.splitlines() if ln.strip()] if res.returncode == 0 else []
    return [ln for ln in _read_crontab().splitlines() if CRON_MARK in ln]
