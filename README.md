# claude-job-hunter

A Claude plugin for an honest, careful job search. Five skills turn Claude into an assistant that finds matching jobs, proves every link is live, tailors ATS-safe CVs from your real experience, keeps your application tracker up to date and prepares you for interviews.

**It never invents experience, never applies for you, and never sends an email.**

## What is inside

| Skill | What it does |
|---|---|
| `setup-profile` | Builds your `career-profile.md`, the single source of facts. Three ways in: **upload your CV (PDF/DOCX)**, **an interview**, or **fill a template by hand**. |
| `cv-job-tailoring` | Scores your fit for a posting (must-haves ×3, nice-to-haves ×1), and only above your threshold builds a one-column, ATS-safe PDF CV with the posting's keywords you truly have. Also drafts cover notes and form answers in your voice. |
| `daily-job-search` | Searches company career pages first, then ATS boards and job boards, and LinkedIn only as a last resort. Opens every link in a real browser before it counts, saves only matches above your threshold, and reports a per-platform checklist. |
| `weekly-tracker` | Reads your application emails (confirmations, rejections, interview invitations) and updates a colour-coded Excel tracker. |
| `interview-prep` | Company brief, a STAR story bank mapped to the posting, likely questions with answers you can say out loud, technical deep dives and questions to ask. |

Plus `scripts/ats_cv_generator.js` (JSON → DOCX → PDF CV) and templates for the profile and the CV.

## Install

### Claude (claude.ai web or desktop)
1. Download the latest `job-hunter.zip` from [Releases](../../releases) (or **Code → Download ZIP** and zip the `plugins/job-hunter` folder).
2. In Claude, open **Customize → Plugins → Add → Upload plugin** and choose the zip.
3. Turn on code execution in settings if it is off. Skills need it.

### Claude Code
```
/plugin marketplace add OmarKAly22/claude-job-hunter
/plugin install job-hunter@claude-job-hunter
```

## Get started
1. Say: **"Set up my career profile"** and attach your CV, or choose the interview or the template.
2. Review the profile. Every number on your CVs comes from its "Confirmed numbers" list, so check them carefully.
3. Paste a job link and say **"Tailor my CV to this job"**.
4. Say **"Run my job search"** to find new matches, then ask Claude to make it a daily scheduled task once you trust the results.
5. Say **"Prepare me for my interview with <company>"** when you get one.

## Requirements
- Code execution enabled (for the CV generator: Node.js with `docx`, LibreOffice for PDF conversion; Claude installs them in its workspace).
- A browser tool for the job search (the Claude desktop app's built-in browser or Claude in Chrome). Without it, links cannot be verified and no leads are saved.
- Optional: an email connector (Gmail) for alert emails and the tracker; an Indeed connector.

## Principles
- **Your facts only.** Skills read `career-profile.md` and what you say. Numbers must be confirmed by you. Known gaps are never claimed.
- **Proof, not promises.** A job counts only after its page was opened and seen live in this run. Search results and cached pages are not proof.
- **Honest scoring.** Below your threshold (default 70%) Claude explains why instead of building a CV.
- **You stay in control.** No applications, no emails sent, no sign-ins, no CAPTCHAs. The only optional inbox change is marking processed job emails as read.
- **ATS-safe by default.** One column, real text, contact details in the body, standard headings, two pages.

## Privacy
Your `career-profile.md` and `cv_base.json` contain personal data. They are in `.gitignore`. Keep them in your own Claude project or folder, never in a public fork.

## Contributing
Issues and pull requests are welcome: more country job boards, ATS closed-page signs, translations of CV section labels.

## License
MIT, see [LICENSE](LICENSE).
