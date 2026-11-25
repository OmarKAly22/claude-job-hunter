# Changelog

Each edition has its own version and tag: `pro-vX.Y.Z` and `free-vX.Y.Z`.

## Pro 0.2.0 – 2026-11-25
- The plugin is now **Job Hunter Pro** (`job-hunter-pro`), for Claude Pro, Max, Team and Enterprise. The skills work as in 0.1.0.
- `cv-job-tailoring` can also check links with the local engine and accepts leads from the engine's export.
- **Claude Code:** the plugin was renamed from `job-hunter` to `job-hunter-pro`. Run `/plugin uninstall job-hunter@claude-job-hunter`, then `/plugin install job-hunter-pro@claude-job-hunter`.

## Free 0.2.0 – 2026-11-25
- First release of **Job Hunter Free** (`job-hunter-free`), for the Claude Free plan.
- Same `setup-profile`, `cv-job-tailoring` and `interview-prep` skills as Pro.
- New `daily-job-search` and `weekly-tracker` that work without a browser connector or scheduled tasks, plus a manual mode for pasted links.
- New `setup-engine` skill: writes the engine config from the career profile and finds the target employers' job boards.
- New **local engine** (`job-hunter-engine`, Python, MIT): public job-board APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Personio, Recruitee, Workday, Bundesagentur für Arbeit), headless-browser link checks (Playwright, or the installed Chrome or Edge), read-only IMAP reader for job emails, desktop and email notifications, scheduling with launchd, cron or Task Scheduler, and a local MCP server for Claude Desktop.
- The release also contains a skills-only zip for accounts that can upload skills but not plugins.

## 0.1.0 – 2026-11-24
- First version (now the Pro edition): `setup-profile`, `cv-job-tailoring`, `daily-job-search`, `weekly-tracker`, `interview-prep`.
- ATS CV generator (JSON → DOCX → PDF) and templates for the profile and the CV.
