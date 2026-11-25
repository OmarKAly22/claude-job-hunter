"""Tell the user a run finished: a desktop notification and, optionally, an email to themselves."""
from __future__ import annotations

import logging
import shutil
import smtplib
import subprocess
import sys
from email.message import EmailMessage

from .config import NotifyConfig, get_secret

log = logging.getLogger("job_hunter")


def desktop(title: str, message: str) -> bool:
    try:
        if sys.platform == "darwin":
            script = f'display notification {_applescript(message)} with title {_applescript(title)}'
            subprocess.run(["osascript", "-e", script], check=True, timeout=10, capture_output=True)
        elif sys.platform.startswith("win"):
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;$n.Icon=[System.Drawing.SystemIcons]::Information;"
                f"$n.Visible=$true;$n.ShowBalloonTip(8000,{_ps(title)},{_ps(message)},'Info');Start-Sleep 9;$n.Dispose()"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=30, capture_output=True)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=True, timeout=10, capture_output=True)
        else:
            return False
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        log.info("desktop notification failed: %s", exc)
        return False


def _applescript(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _ps(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def email_self(cfg: NotifyConfig, subject: str, body: str) -> bool:
    """Send a note to the user's own address. Only ever to cfg.email_to, which the user set."""
    if not cfg.email_to:
        return False
    password = get_secret(cfg.password_env, "smtp")
    if not password or not cfg.smtp_host:
        log.warning("email notification skipped: set smtp_host and %s (or job-hunter set-password smtp)", cfg.password_env)
        return False
    msg = EmailMessage()
    msg["From"] = cfg.smtp_user or cfg.email_to
    msg["To"] = cfg.email_to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(cfg.smtp_user or cfg.email_to, password)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.warning("email notification failed: %s", exc)
        return False


def announce(cfg: NotifyConfig, title: str, message: str, details: str = "") -> None:
    if cfg.desktop:
        desktop(title, message)
    if cfg.email_to:
        email_self(cfg, f"{title}: {message}", details or message)
