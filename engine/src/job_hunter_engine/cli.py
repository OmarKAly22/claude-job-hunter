"""Command line for the Job Hunter engine.  Run `job-hunter --help`."""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .config import ConfigError, example_config_text, load_config, resolve_config_path


def _setup_logging(verbose: bool, log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True)


def cmd_init(args: argparse.Namespace) -> int:
    path = resolve_config_path(args.config)
    if path.exists() and not args.force:
        print(f"{path} already exists (use --force to overwrite).")
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(example_config_text(), encoding="utf-8")
    print(f"Wrote {path}\nEdit it (or let the setup-engine skill in Claude fill it in), then run: job-hunter doctor")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from .verify import browser_available

    ok = True
    print(f"job-hunter-engine {__version__}, Python {sys.version.split()[0]}")
    try:
        cfg = load_config(args.config)
        print(f"✅ config {cfg.path}: {len(cfg.employers)} employer board(s), "
              f"Arbeitsagentur {'on' if cfg.arbeitsagentur.enabled else 'off'}, inbox {'on' if cfg.inbox.enabled else 'off'}")
        print(f"✅ output folder {cfg.output_folder}")
    except ConfigError as exc:
        print(f"❌ config: {exc}")
        return 1
    if cfg.verify.browser:
        b_ok, note = browser_available()
        print(f"{'✅' if b_ok else '⚠️ '} browser: {note}")
        ok &= b_ok
    else:
        print("⚠️  browser: disabled in config (links are proven by the ATS listing only)")
    try:
        import mcp  # noqa: F401
        print("✅ MCP: installed (Claude Desktop can call the engine; see: job-hunter claude-config)")
    except ImportError:
        print("⚠️  MCP: not installed (pip install 'job-hunter-engine[mcp]'); use the leads JSON upload instead")
    if cfg.inbox.enabled:
        from .config import get_secret
        has = bool(get_secret(cfg.inbox.password_env, "inbox"))
        print(f"{'✅' if has else '❌'} inbox password: {'found' if has else 'missing (job-hunter set-password inbox)'}")
        ok &= has
    if args.online:
        from .net import Http, HttpError
        from .sources import FETCHERS
        http = Http()
        for emp in cfg.employers:
            try:
                jobs = FETCHERS[emp.ats](http, emp, cfg.search.titles)
                print(f"✅ {emp.name} ({emp.ats}): {len(jobs)} open jobs on the board")
            except (HttpError, ValueError, KeyError) as exc:
                ok = False
                print(f"❌ {emp.name} ({emp.ats}): {str(exc)[:200]}")
    else:
        print("Tip: add --online to test every employer board.")
    return 0 if ok else 2


def cmd_setup_browser(args: argparse.Namespace) -> int:
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("Playwright is missing. Install the engine with the browser extra:\n"
              "  pipx install 'job-hunter-engine[all] @ git+https://github.com/OmarKAly22/claude-job-hunter@free-v"
              f"{__version__}#subdirectory=engine'")
        return 1
    return subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"])


def cmd_set_password(args: argparse.Namespace) -> int:
    try:
        import keyring
    except ImportError:
        print("keyring is not installed (pip install 'job-hunter-engine[keyring]'), "
              "so use an environment variable instead (see password_env in the config).")
        return 1
    secret = getpass.getpass(f"Password for {args.which} (stored in your OS keychain): ")
    if not secret:
        print("Nothing stored.")
        return 1
    keyring.set_password("job-hunter", args.which, secret)
    print("Stored.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .notify import announce
    from .pipeline import run_search

    cfg = load_config(args.config)
    _setup_logging(True, cfg.output_folder / "logs" / "search.log")
    result = run_search(cfg, max_new=args.max_new, progress=None if args.quiet else lambda m: print(m, file=sys.stderr))
    print(json.dumps({
        "summary": result.summary(),
        "export": str(result.export_path),
        "check_method": result.check_method,
        "sources": [r.__dict__ for r in result.reports],
    }, indent=1, ensure_ascii=False))
    if args.notify:
        lines = [f"{j.company} – {j.title} ({j.location})" for j in result.live[:15]]
        announce(cfg.notify, "Job Hunter", result.summary(),
                 "\n".join(lines) + f"\n\nOpen Claude and say: score today's leads.\nFile: {result.export_path}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from .pipeline import verify_urls

    cfg = load_config(args.config)
    print(json.dumps(verify_urls(cfg, args.urls), indent=1, ensure_ascii=False))
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    from .inbox import export_inbox, fetch_imap, parse_eml_files
    from .notify import announce

    cfg = load_config(args.config)
    _setup_logging(True, cfg.output_folder / "logs" / "inbox.log")
    if args.eml:
        emails = parse_eml_files(Path(p) for p in args.eml)
    else:
        if not cfg.inbox.enabled:
            print("Inbox reading is off. Set [inbox] enabled = true, or pass .eml files with --eml.")
            return 1
        emails = fetch_imap(cfg.inbox, args.days)
    path = export_inbox(cfg, emails)
    counts: dict[str, int] = {}
    for e in emails:
        counts[e.category] = counts.get(e.category, 0) + 1
    print(json.dumps({"export": str(path), "counts": counts}, indent=1))
    if args.notify:
        msg = ", ".join(f"{v} {k}" for k, v in counts.items()) or "no job emails"
        announce(cfg.notify, "Job Hunter inbox", msg, f"Open Claude and say: update my tracker.\nFile: {path}")
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    from . import schedule

    if args.action == "show":
        lines = schedule.show()
        print("\n".join(lines) if lines else "Nothing scheduled.")
        return 0
    if args.action == "remove":
        removed = schedule.remove()
        print("Removed: " + ", ".join(removed) if removed else "Nothing to remove.")
        return 0
    cfg = load_config(args.config)
    jobs = [schedule.parse_when("search", args.search_time, args.search_days)]
    if args.inbox_time:
        jobs.append(schedule.parse_when("inbox", args.inbox_time, args.inbox_days))
    log_dir = cfg.output_folder / "logs"
    if args.dry_run:
        print("\n".join(schedule.plan(jobs, cfg.path, log_dir)))
        return 0
    for line in schedule.install(jobs, cfg.path, log_dir):
        print(f"Scheduled {line}")
    print("Your computer must be switched on (macOS also runs a missed job when it wakes). Undo with: job-hunter schedule remove")
    return 0


def cmd_claude_config(args: argparse.Namespace) -> int:
    path = resolve_config_path(args.config)
    snippet = {"mcpServers": {"job-hunter": {
        "command": sys.executable, "args": ["-m", "job_hunter_engine", "mcp", "--config", str(path)]}}}
    print("Add this to Claude Desktop's config (Settings > Developer > Edit Config), then restart Claude Desktop:\n")
    print(json.dumps(snippet, indent=2))
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp_server import serve

    _setup_logging(False)
    serve(args.config)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-hunter", description="Local engine for the Job Hunter Free edition.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, func, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument("--config", help="config file (default: $JOB_HUNTER_CONFIG or ~/JobHunter/config.toml)")
        p.set_defaults(func=func)
        return p

    p = add("init", cmd_init, "write an example config file")
    p.add_argument("--force", action="store_true")
    p = add("doctor", cmd_doctor, "check the config, browser, MCP and passwords")
    p.add_argument("--online", action="store_true", help="also call every employer board once")
    add("setup-browser", cmd_setup_browser, "download the headless Chromium used for link checks")
    p = add("set-password", cmd_set_password, "store the IMAP or SMTP password in your OS keychain")
    p.add_argument("which", choices=["inbox", "smtp"])
    p = add("run", cmd_run, "search all sources, check links, write leads JSON")
    p.add_argument("--max-new", type=int, help="stop after this many new live jobs")
    p.add_argument("--notify", action="store_true", help="desktop/email notification when done")
    p.add_argument("--quiet", action="store_true")
    p = add("verify", cmd_verify, "check whether job links are live")
    p.add_argument("urls", nargs="+")
    p = add("inbox", cmd_inbox, "read job emails (read-only) and write inbox JSON")
    p.add_argument("--days", type=int, help="look back this many days (default from config)")
    p.add_argument("--eml", nargs="+", help="read exported .eml files instead of IMAP")
    p.add_argument("--notify", action="store_true")
    p = add("schedule", cmd_schedule, "run the search (and inbox) on your computer's scheduler")
    p.add_argument("action", choices=["install", "remove", "show"])
    p.add_argument("--search-time", default="07:00", help="HH:MM (default 07:00)")
    p.add_argument("--search-days", default="weekdays", help="daily | weekdays | mon,wed,fri (default weekdays)")
    p.add_argument("--inbox-time", help="HH:MM to also read job emails, e.g. 07:30")
    p.add_argument("--inbox-days", default="mon", help="days for the inbox run (default mon)")
    p.add_argument("--dry-run", action="store_true", help="show what would be scheduled")
    add("claude-config", cmd_claude_config, "print the Claude Desktop MCP config for this engine")
    add("mcp", cmd_mcp, "run as a local MCP server (started by Claude Desktop)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command not in ("run", "inbox", "mcp"):
        _setup_logging(False)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Config problem: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(f"({datetime.now():%Y-%m-%d %H:%M})", file=sys.stderr)
        return 1
