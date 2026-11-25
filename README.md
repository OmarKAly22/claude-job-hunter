# claude-job-hunter

A Claude plugin for an honest, careful job search. It finds matching jobs, proves every link is live, tailors ATS-safe CVs from your real experience, keeps your application tracker up to date and prepares you for interviews.

**It never invents experience, never applies for you, and never sends an email.**

## Which edition do I need?

| You have… | Get | Download |
|---|---|---|
| **Claude Pro, Max, Team or Enterprise** | **Job Hunter Pro** | [job-hunter-pro-0.2.0.zip](https://github.com/OmarKAly22/claude-job-hunter/releases/download/pro-v0.2.0/job-hunter-pro-0.2.0.zip) · [release notes](https://github.com/OmarKAly22/claude-job-hunter/releases/tag/pro-v0.2.0) |
| **Claude Free**, or you want job search to run on your own computer | **Job Hunter Free** | [job-hunter-free-0.2.0.zip](https://github.com/OmarKAly22/claude-job-hunter/releases/download/free-v0.2.0/job-hunter-free-0.2.0.zip) · [release notes](https://github.com/OmarKAly22/claude-job-hunter/releases/tag/free-v0.2.0) |

All releases: [Pro](https://github.com/OmarKAly22/claude-job-hunter/releases?q=pro-v&expanded=true) · [Free](https://github.com/OmarKAly22/claude-job-hunter/releases?q=free-v&expanded=true)

Both editions share the same profile setup, CV tailoring and interview prep. They differ in **how jobs are found, checked and tracked**:

| | Pro | Free |
|---|---|---|
| Profile setup, CV tailoring, match score, interview prep | ✅ | ✅ same skills |
| Finding jobs | Claude browses career pages, ATS boards and job boards | A local engine queries the employers' public job-board APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Personio, Recruitee, Workday) and the Bundesagentur für Arbeit |
| Proving a link is live | Claude in Chrome or the Claude desktop app's built-in browser | Headless browser on your computer (Playwright, or your installed Chrome) |
| Application tracker | Reads your Gmail through the connector | A connected email app, or the engine reads your mailbox over IMAP (read-only), or you upload `.eml` files |
| Daily / weekly runs | Claude scheduled tasks | Your computer's own scheduler (launchd, cron, Task Scheduler) |
| You need | A paid Claude plan | Python 3.11+ on your computer, about 10 minutes of setup |
| Job boards like StepStone or LinkedIn | Searched (signed out, LinkedIn last) | Not scraped. Use the Bundesagentur source, or paste links you found |

## What is inside

| Skill | Edition | What it does |
|---|---|---|
| `setup-profile` | both | Builds your `career-profile.md`, the single source of facts. Three ways in: **upload your CV (PDF/DOCX)**, **an interview**, or **fill a template by hand**. |
| `cv-job-tailoring` | both | Scores your fit for a posting (must-haves ×3, nice-to-haves ×1), and only above your threshold builds a one-column, ATS-safe PDF CV with the posting's keywords you truly have. Also drafts cover notes and form answers in your voice. |
| `interview-prep` | both | Company brief, a STAR story bank mapped to the posting, likely questions with answers you can say out loud, technical deep dives and questions to ask. |
| `daily-job-search` | Pro | Searches company career pages first, then ATS boards and job boards, and LinkedIn only as a last resort. Opens every link in a real browser before it counts. |
| `weekly-tracker` | Pro | Reads your application emails in Gmail and updates a colour-coded Excel tracker. |
| `daily-job-search` | Free | Scores the jobs the local engine found and proved live, saves the matches, builds CVs and reports a per-source checklist. Has a manual mode for pasted links. |
| `weekly-tracker` | Free | The same tracker, fed by a connected email app, the engine's IMAP reader, `.eml` files or pasted emails. |
| `setup-engine` | Free | Writes the engine's config from your profile, finds your target employers' job boards and walks you through install, testing and scheduling. |

Plus `scripts/ats_cv_generator.js` (JSON → DOCX → PDF CV) and templates for the profile and the CV.

## Install: Job Hunter Pro

**Claude (claude.ai web or desktop)**
1. Download [job-hunter-pro-0.2.0.zip](https://github.com/OmarKAly22/claude-job-hunter/releases/download/pro-v0.2.0/job-hunter-pro-0.2.0.zip).
2. In Claude, open **Customize → Plugins → Add → Upload plugin** and choose the zip.
3. Turn on code execution in settings if it is off. Skills need it.
4. For the job search, use the Claude desktop app's built-in browser or install Claude in Chrome. For the tracker, connect Gmail.

**Claude Code**
```
/plugin marketplace add OmarKAly22/claude-job-hunter
/plugin install job-hunter-pro@claude-job-hunter
```

## Install: Job Hunter Free

**1. The plugin (in Claude)**
1. Download [job-hunter-free-0.2.0.zip](https://github.com/OmarKAly22/claude-job-hunter/releases/download/free-v0.2.0/job-hunter-free-0.2.0.zip).
2. In Claude, open **Customize → Plugins → Add → Upload plugin** and choose the zip. If your account cannot upload plugins, download [job-hunter-free-skills-0.2.0.zip](https://github.com/OmarKAly22/claude-job-hunter/releases/download/free-v0.2.0/job-hunter-free-skills-0.2.0.zip), unpack it and upload each skill zip under **Customize → Skills**.
3. Turn on code execution (Settings → Capabilities). Skills need it.

**2. The engine (on your computer)**
```bash
pipx install "job-hunter-engine[all] @ git+https://github.com/OmarKAly22/claude-job-hunter@free-v0.2.0#subdirectory=engine"
job-hunter setup-browser     # skip if Google Chrome is installed
job-hunter init
```
Then say **"Set up my job hunter engine"** in Claude. It writes your `config.toml` and walks you through the rest. Details: [engine/README.md](engine/README.md).

**Claude Code**
```
/plugin marketplace add OmarKAly22/claude-job-hunter
/plugin install job-hunter-free@claude-job-hunter
```

## Get started
1. Say **"Set up my career profile"** and attach your CV, or choose the interview or the template.
2. Review the profile. Every number on your CVs comes from its "Confirmed numbers" list, so check them carefully.
3. Paste a job link and say **"Tailor my CV to this job"**.
4. **Pro:** say **"Run my job search"**, then ask Claude to make it a daily scheduled task once you trust the results.
   **Free:** run `job-hunter run` (or schedule it with `job-hunter schedule install`), then say **"Score today's leads"** in Claude.
5. Say **"Prepare me for my interview with <company>"** when you get one.

## Principles
- **Your facts only.** Skills read `career-profile.md` and what you say. Numbers must be confirmed by you. Known gaps are never claimed.
- **Proof, not promises.** A job counts only after its page was opened and seen live. Search results and cached pages are not proof. In the Free edition, the engine records how each link was proven (`browser` or the employer's live `ats-api` listing).
- **Honest scoring.** Below your threshold (default 70%) Claude explains why instead of building a CV.
- **You stay in control.** No applications, no emails sent, no sign-ins, no CAPTCHAs, no scraping of sites that forbid it.
- **ATS-safe by default.** One column, real text, contact details in the body, standard headings, two pages.

## Privacy
Your `career-profile.md`, `cv_base.json` and the engine's `config.toml` contain personal data. They are in `.gitignore`. Keep them in your own Claude project or folder, never in a public fork. The engine reads mailbox passwords from an environment variable or your OS keychain, never from a file.

## Repository layout and releases
```
shared/            skills, scripts and templates used by both editions
editions/pro/      Pro-only skills and plugin.json
editions/free/     Free-only skills and plugin.json
engine/            the Free edition's local engine (Python)
plugins/           built plugins (generated, do not edit): job-hunter-pro, job-hunter-free
scripts/           build_editions.py, set_version.py
```
Each edition has its own version and tag series: `pro-vX.Y.Z` and `free-vX.Y.Z`. To release one:
```bash
python scripts/set_version.py free <X.Y.Z>     # updates versions, links and plugins/
# add a "## Free <X.Y.Z> – <date>" section to CHANGELOG.md, open a PR, merge
git tag free-v<X.Y.Z> && git push origin free-v<X.Y.Z>
```
The release workflow builds the zips, the engine wheel and a release named "Job Hunter Free v<X.Y.Z> (Claude Free + local engine)". If a release run fails (for example on a GitHub API error), re-run it from **Actions → Release → Run workflow** with the tag name; it cleans up any leftover draft. The old `v0.1.0` release is the Pro edition before the split.

## Contributing
Issues and pull requests are welcome: more ATS sources for the engine, more country job boards, ATS closed-page signs, translations of CV section labels. Change `shared/` or `editions/`, then run `python scripts/build_editions.py`.

## License
MIT, see [LICENSE](LICENSE).
