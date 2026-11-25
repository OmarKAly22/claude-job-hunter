import json
import sys
from email.message import EmailMessage
from pathlib import Path

import pytest

from job_hunter_engine import schedule
from job_hunter_engine.cli import main
from job_hunter_engine.config import ConfigError, load_config
from job_hunter_engine.inbox import classify, export_inbox, parse_eml_files, parse_message


def _mail(subject, body, sender="no-reply@greenhouse.io", html=False):
    msg = EmailMessage()
    msg["From"] = f"Acme Recruiting <{sender}>"
    msg["To"] = "me@example.com"
    msg["Subject"] = subject
    msg["Date"] = "Mon, 23 Nov 2026 09:15:00 +0100"
    msg["Message-ID"] = "<abc@example.com>"
    if html:
        msg.set_content("plain fallback")
        msg.add_alternative(f"<html><body><p>{body}</p></body></html>", subtype="html")
    else:
        msg.set_content(body)
    return msg.as_bytes()


def test_classification():
    assert parse_message(_mail("Interview invitation – Data Engineer", "We would like to invite you")).category == "interview"
    assert parse_message(_mail("Your application", "Unfortunately we decided to move forward with other candidates")).category == "rejection"
    assert parse_message(_mail("Eingangsbestätigung Ihrer Bewerbung", "Vielen Dank für Ihre Bewerbung")).category == "confirmation"
    assert parse_message(_mail("5 new jobs for you", "Data Engineer at X", sender="jobalerts-noreply@linkedin.com")).category == "job_alert"
    assert parse_message(_mail("Newsletter", "Unfortunately the sale ended", sender="shop@example.com")) is None
    assert classify("Next steps for your order", "track your parcel", "shop@example.com") is None


def test_eml_files_and_export(tmp_path, write_config):
    eml = tmp_path / "a.eml"
    eml.write_bytes(_mail("Absage", "Leider müssen wir Ihnen mitteilen, Ihre Bewerbung", sender="jobs@personio.de", html=True))
    emails = parse_eml_files([eml])
    assert emails[0].category == "rejection" and emails[0].date == "2026-11-23"
    cfg = load_config(write_config('[search]\ntitles = ["x"]\n'))
    path = export_inbox(cfg, emails)
    assert json.loads(path.read_text())["counts"] == {"rejection": 1}


def test_parse_when():
    job = schedule.parse_when("search", "7:05", "weekdays")
    assert (job.hour, job.minute, job.days) == (7, 5, ["mon", "tue", "wed", "thu", "fri"])
    assert schedule.parse_when("inbox", "07:30", "mon").days == ["mon"]
    assert schedule.parse_when("search", "23:59", "daily").days == []
    with pytest.raises(ValueError):
        schedule.parse_when("search", "25:00", "daily")
    with pytest.raises(ValueError):
        schedule.parse_when("search", "07:00", "funday")


def test_cron_and_launchd_entries(tmp_path):
    job = schedule.parse_when("search", "07:00", "mon,wed")
    line = schedule._cron_line(job, tmp_path / "config.toml", tmp_path / "logs")
    assert line.startswith("0 7 * * 1,3 ") and line.endswith("# job-hunter-engine:search")
    assert "job_hunter_engine run --config" in line
    import plistlib
    plist = plistlib.loads(schedule._launchd_plist(job, tmp_path / "c.toml", tmp_path / "logs"))
    assert plist["StartCalendarInterval"] == [{"Weekday": 1, "Hour": 7, "Minute": 0}, {"Weekday": 3, "Hour": 7, "Minute": 0}]
    assert plist["ProgramArguments"][:3] == [sys.executable, "-m", "job_hunter_engine"]
    win = schedule._win_args(job, tmp_path / "c.toml")
    assert win[win.index("/SC") + 1] == "WEEKLY" and win[win.index("/D") + 1] == "MON,WED"


def test_config_errors(write_config):
    with pytest.raises(ConfigError, match="titles"):
        load_config(write_config("[search]\n"))
    with pytest.raises(ConfigError, match="ats must be"):
        load_config(write_config('[search]\ntitles=["x"]\n[[employers]]\nname="A"\nats="taleo"\nslug="a"\n'))
    with pytest.raises(ConfigError, match="board_url"):
        load_config(write_config('[search]\ntitles=["x"]\n[[employers]]\nname="A"\nats="workday"\n'))
    with pytest.raises(ConfigError, match="unknown keys"):
        load_config(write_config('[search]\ntitles=["x"]\ntitle="typo"\n'))


def test_example_config_loads_and_cli_init(tmp_path, capsys):
    path = tmp_path / "cfg" / "config.toml"
    assert main(["init", "--config", str(path)]) == 0
    cfg = load_config(path)
    assert cfg.employers[0].ats == "greenhouse" and cfg.output_folder == Path("~/JobHunter").expanduser()
    assert main(["init", "--config", str(path)]) == 1  # refuses to overwrite
    assert main(["schedule", "install", "--config", str(path), "--dry-run", "--inbox-time", "07:30"]) == 0
    out = capsys.readouterr().out
    assert "search" in out and "inbox" in out
    assert main(["claude-config", "--config", str(path)]) == 0
    assert '"mcp"' in capsys.readouterr().out
