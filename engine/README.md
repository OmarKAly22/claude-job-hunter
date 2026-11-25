# Job Hunter engine (for the Free edition)

A small open-source program that runs **on your own computer** and does the parts of the job search that would otherwise need paid Claude features:

| Instead of (paid) | The engine uses (free) |
|---|---|
| Claude in Chrome / built-in browser for link checks | Headless Chromium through Playwright (or your installed Chrome / Edge) |
| Browsing job boards | Public job-board APIs of the employers' applicant tracking systems: Greenhouse, Lever, Ashby, SmartRecruiters, Personio, Recruitee, Workday, plus the Bundesagentur für Arbeit (Germany) |
| Gmail connector for the tracker | IMAP, read-only (works with Gmail, Outlook, GMX, web.de, any provider) |
| Scheduled tasks | Your computer's own scheduler: launchd (macOS), cron (Linux), Task Scheduler (Windows) |

The engine **does not score jobs or write CVs**. Claude does that with the Free edition's skills. The engine never applies, never signs in to job sites, never solves CAPTCHAs and never sends email, apart from an optional "run finished" note to your own address.

## Install (once)

You need Python 3.11 or newer and [pipx](https://pipx.pypa.io).

```bash
pipx install "job-hunter-engine[all] @ git+https://github.com/OmarKAly22/claude-job-hunter@free-v0.2.0#subdirectory=engine"
job-hunter setup-browser      # downloads headless Chromium (skip if Google Chrome is installed)
job-hunter init               # writes ~/JobHunter/config.toml
```

Fill in `~/JobHunter/config.toml`. The easiest way is to say **"Set up my job hunter engine"** in Claude with the Free edition installed: the `setup-engine` skill builds the file from your career profile and finds your target employers' job boards. Then check it:

```bash
job-hunter doctor --online
```

## Use

```bash
job-hunter run                # search, check links, write ~/JobHunter/latest-leads.json
job-hunter inbox              # read job emails, write ~/JobHunter/latest-inbox.json
job-hunter verify <url> ...   # recheck links
```

Then, in Claude, either:
- **Claude Desktop with the engine connected (MCP):** say *"Score today's leads"*. Claude calls the engine itself. Connect it with `job-hunter claude-config`, paste the printed block into Claude Desktop's config (Settings → Developer → Edit Config) and restart Claude Desktop.
- **Any Claude (web, desktop, mobile):** upload `latest-leads.json` (or `latest-inbox.json`) and say *"Score these leads"* (or *"Update my tracker"*).

## Run it every day

```bash
job-hunter schedule install --search-time 07:00 --search-days weekdays --inbox-time 07:30 --inbox-days mon
job-hunter schedule show
job-hunter schedule remove
```

Your computer must be on at that time. On macOS, launchd also runs a missed job when the Mac wakes up. After each run you get a desktop notification. Set `[notify] email_to` for an email too.

## Passwords

The IMAP (and optional SMTP) password is read from an environment variable, or from your OS keychain after `job-hunter set-password inbox`. Gmail needs an [app password](https://myaccount.google.com/apppasswords). The password is never written to the config or the output files.

## How a job is proven live

1. Only jobs from the employer's **live ATS listing in this run** are considered, and listings remove closed jobs.
2. Each job page is opened in the headless browser: the final URL must still be that single job, the page must show the same title, and no "closed" sign may appear (English and German phrases).
3. If the page cannot be read (some boards block headless browsers), the job is kept only because the employer's live listing returned it in this run, and it is marked `verification: ats-api`. A page that says the job is closed always wins.

Every job in the export has `verification` (`browser` or `ats-api`) and `link_proof`.

## Output files (in the output folder)

- `latest-leads.json` and `leads/leads-<date>.json`: live jobs with description, plus a per-source checklist and the jobs that were not saved, with reasons.
- `latest-inbox.json` and `inbox/inbox-<date>.json`: job emails by category (interview, rejection, closed, confirmation, job_alert, other_ats).
- `state.json`: every job already handed over, so it is never sent twice. Delete it to start over.
- `logs/`: run logs.

## Development

```bash
cd engine
pip install -e ".[dev,all]"
pytest
```
