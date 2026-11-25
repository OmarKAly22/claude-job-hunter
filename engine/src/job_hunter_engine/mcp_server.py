"""Local MCP server for Claude Desktop, so Claude can call the engine directly.

Claude Desktop starts it with:  job-hunter mcp --config ~/JobHunter/config.toml
All tools only read the web and your mailbox; none of them applies, signs in or sends anything.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .config import Config, load_config
from .inbox import export_inbox, fetch_imap
from .pipeline import latest_leads, run_search, verify_urls
from .verify import browser_available


def _server_class() -> Any:
    try:  # mcp >= 2
        from mcp.server.mcpserver import MCPServer

        return MCPServer
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP

        return FastMCP


def build_server(config_path: str | None) -> Any:
    server = _server_class()(
        "job-hunter",
        instructions=(
            "Local Job Hunter engine. Use run_job_search (or get_latest_leads after a scheduled run) to get "
            "verified job leads, verify_job_links to recheck links, and read_job_emails for the application "
            "tracker. Score and tailor with the job-hunter-free skills; the engine never scores."
        ),
    )

    def cfg() -> Config:
        return load_config(config_path)

    @server.tool()
    def engine_status() -> dict[str, Any]:
        """Show the engine version, config file, output folder, whether the headless browser works,
        and when the last search and inbox exports were written."""
        c = cfg()
        ok, note = browser_available() if c.verify.browser else (False, "disabled in config")
        out: dict[str, Any] = {
            "engine_version": __version__,
            "config": str(c.path),
            "output_folder": str(c.output_folder),
            "employers": len(c.employers),
            "arbeitsagentur": c.arbeitsagentur.enabled,
            "inbox": c.inbox.enabled,
            "browser": {"ok": ok, "note": note},
        }
        for name in ("latest-leads.json", "latest-inbox.json"):
            path = c.output_folder / name
            if path.exists():
                out[name] = json.loads(path.read_text(encoding="utf-8")).get("generated_at")
        return out

    @server.tool()
    def run_job_search(max_new: int | None = None) -> dict[str, Any]:
        """Run a full search now: fetch every configured job source, keep in-scope roles not handed over before,
        open each link in the headless browser and export the live ones. Can take several minutes.
        Returns the per-source checklist; call get_latest_leads for the jobs themselves."""
        result = run_search(cfg(), max_new=max_new)
        return {
            "summary": result.summary(),
            "check_method": result.check_method,
            "stopped_at_limit": result.stopped_early,
            "export": str(result.export_path),
            "sources": [r.__dict__ for r in result.reports],
            "not_saved": len(result.rejected),
        }

    @server.tool()
    def get_latest_leads(offset: int = 0, limit: int = 10, include_descriptions: bool = True) -> dict[str, Any]:
        """Return live jobs from the most recent search export (scheduled or manual), a page at a time.
        Each job has company, title, url, location, posted, description, verification and link_proof."""
        data = latest_leads(cfg())
        if data is None:
            return {"error": "No search has run yet. Call run_job_search, or run 'job-hunter run' on the computer."}
        jobs = data.get("jobs", [])
        page = jobs[offset: offset + limit]
        if not include_descriptions:
            page = [{k: v for k, v in j.items() if k != "description"} for j in page]
        return {
            "generated_at": data.get("generated_at"),
            "summary": data.get("summary"),
            "check_method": data.get("check_method"),
            "total": len(jobs),
            "offset": offset,
            "jobs": page,
            "next_offset": offset + limit if offset + limit < len(jobs) else None,
            "sources": data.get("sources") if offset == 0 else None,
            "not_saved": data.get("not_saved") if offset == 0 else None,
        }

    @server.tool()
    def verify_job_links(urls: list[str], expected_titles: list[str] | None = None) -> list[dict[str, str]]:
        """Open each URL in the headless browser and report live, dead or unverifiable, with the proof
        (page title) or reason. Pass the expected job titles in the same order when known."""
        return verify_urls(cfg(), urls[:40], expected_titles)

    @server.tool()
    def read_job_emails(days: int | None = None) -> dict[str, Any]:
        """Read job-related emails from the configured mailbox (read-only: nothing is marked, moved or sent).
        Returns confirmations, rejections, interview invitations, closed-role notices and job alerts."""
        c = cfg()
        if not c.inbox.enabled:
            return {"error": "Inbox reading is off. Set [inbox] enabled = true in the config."}
        emails = fetch_imap(c.inbox, days)
        path = export_inbox(c, emails)
        return json.loads(Path(path).read_text(encoding="utf-8"))

    return server


def serve(config_path: str | None) -> None:
    build_server(config_path).run()
