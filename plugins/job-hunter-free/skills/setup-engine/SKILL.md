---
name: setup-engine
description: Free edition. Set up the local Job Hunter engine on the user's computer - write its config.toml from career-profile.md, find the job-board (ATS) of each target employer, and walk the user through installing, testing, connecting to Claude Desktop and scheduling it. Use for "set up my job hunter engine", "install the engine", "add an employer to the engine", or when daily-job-search finds no engine.
---

# Set up the Job Hunter engine (Free edition)

The engine is a small open-source Python program that runs on the user's computer. It finds jobs through public job-board APIs, checks each link in a headless browser, reads job emails over IMAP (read-only) and runs on the computer's own scheduler. Claude then scores the results with `daily-job-search` and `weekly-tracker`. Full details: `engine/README.md` in https://github.com/OmarKAly22/claude-job-hunter.

**Never ask for, accept or write passwords.** The user stores them on their own computer with `job-hunter set-password inbox`.

## 1. Read the profile
Read `career-profile.md` (run `setup-profile` first if it is missing). Take: role titles, countries and places, excluded places and employers, working languages, maximum posting age, target employers, and whether the user wants the email tracker.

## 2. Find each target employer's job board
For each target employer (start with the 30 most important), find which applicant tracking system hosts its jobs and the board name ("slug"):

| ATS | How the careers URL looks | Config |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/<slug>`, `job-boards.greenhouse.io/<slug>`, or `gh_jid=` in the URL | `ats = "greenhouse"`, `slug` |
| Lever | `jobs.lever.co/<slug>` (`jobs.eu.lever.co` → add `region = "eu"`) | `ats = "lever"`, `slug` |
| Ashby | `jobs.ashbyhq.com/<slug>` | `ats = "ashby"`, `slug` |
| SmartRecruiters | `jobs.smartrecruiters.com/<slug>` or `careers.smartrecruiters.com/<slug>` | `ats = "smartrecruiters"`, `slug` |
| Personio | `<slug>.jobs.personio.de` (or `.com` → add `domain = "jobs.personio.com"`) | `ats = "personio"`, `slug` |
| Recruitee | `<slug>.recruitee.com` | `ats = "recruitee"`, `slug` |
| Workday | `<tenant>.wd<N>.myworkdayjobs.com/<locale>/<site>` | `ats = "workday"`, `board_url` = that URL |

Use web search ("<employer> careers jobs") and open the careers page to see where the job links point. Record what you found and how sure you are. Employers on other systems (SuccessFactors, Taleo, iCIMS, softgarden, own portals) cannot be read through a public API: list them for the user under **"Check these career pages yourself"**, and if the user is in Germany, the Bundesagentur für Arbeit source often covers them.

## 3. Write `config.toml`
Start from `templates/engine-config.example.toml` in this plugin and fill it in:
- `[output] folder`: `~/JobHunter` unless the user wants another folder.
- `[search]`: `titles` from the profile's role titles (add the German titles too when German postings are in scope, e.g. "Dateningenieur"); `exclude_title_words` keeps the junior and student defaults plus anything the profile excludes; `locations` lists countries, cities and "Remote" as written in postings (both "Germany" and "Deutschland"); `exclude_employers` from the profile; `max_age_days` from the profile.
- `[[employers]]`: one block per board found in step 2.
- `[arbeitsagentur]`: `enabled = true` when Germany is in scope, `where` = the user's city, `radius_km` from the profile (default 50).
- `[inbox]`: only if the user wants the tracker. Ask for the email address and provider. Use the host for that provider (Gmail `imap.gmail.com`, Outlook/Hotmail `outlook.office365.com`, GMX `imap.gmx.net`, web.de `imap.web.de`, iCloud `imap.mail.me.com`). Gmail and iCloud need an app password.
- `[notify]`: `desktop = true`; `email_to` only if the user asks for an email after each run.

Check the TOML is valid (parse it), then deliver it as a file named `config.toml`.

## 4. Install guide (match the user's operating system)
Give these steps as a short numbered list:
1. Install Python 3.11+ (python.org; on macOS `brew install python`) and pipx (`python -m pip install --user pipx && python -m pipx ensurepath`).
2. `pipx install "job-hunter-engine[all] @ git+https://github.com/OmarKAly22/claude-job-hunter@free-v0.2.0#subdirectory=engine"`
3. `job-hunter setup-browser` (not needed if Google Chrome is installed).
4. Save the delivered `config.toml` as `~/JobHunter/config.toml` (on Windows `%USERPROFILE%\JobHunter\config.toml`).
5. If the tracker is wanted: `job-hunter set-password inbox`.
6. `job-hunter doctor --online`. Every employer must show ✅; for ❌, the user pastes the output here and you fix the slug or remove the employer.
7. First run: `job-hunter run`, then come back and say **"Score today's leads"**.

## 5. Connect it to Claude (optional, Claude Desktop)
`job-hunter claude-config` prints a block for Claude Desktop's config (Settings → Developer → Edit Config). After a restart, Claude can call the engine directly. Without this, the user uploads `~/JobHunter/latest-leads.json` to the chat.

## 6. Schedule it
`job-hunter schedule install --search-time 07:00 --search-days weekdays` (add `--inbox-time 07:30 --inbox-days mon` for the tracker). The computer must be on at that time (a Mac also catches up when it wakes). `job-hunter schedule remove` undoes it.

## Adding or fixing an employer later
Find the board as in step 2 and give the user the exact `[[employers]]` block to add, then `job-hunter doctor --online`.
