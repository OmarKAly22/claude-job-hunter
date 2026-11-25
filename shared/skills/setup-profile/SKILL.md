---
name: setup-profile
description: Create or update the user's career-profile.md and cv_base.json, the single source of facts for CVs, match scores and job searches. Offers three ways in - upload an existing CV (PDF or DOCX), an interactive interview, or a template to fill in by hand. Use before any other job-hunter skill when no profile exists, or when the user's experience, targets or numbers changed.
---

# Set up the career profile

Every other job-hunter skill reads `career-profile.md` (facts, targets, rules) and `cv_base.json` (CV content). This skill creates them. Nothing in them may be invented.

## 0. Check what exists
Look for `career-profile.md` in the conversation, the project files and any connected folder. If it exists, read it, ask what changed, and update only that. Otherwise go to step 1.

## 1. Offer three ways in
Ask once, as a multiple-choice question where the tool exists:

| Option | Best for |
|---|---|
| **A. Upload my CV** (PDF or DOCX, optionally a LinkedIn PDF export too) | Fastest. Claude extracts, the user confirms. |
| **B. Interview me** | No up-to-date CV, or a career change. |
| **C. I'll fill it in by hand** | Users who prefer to write it themselves. |

Options can be combined: an upload followed by a short interview for the gaps is the usual best result.

## 2A. Upload a CV
1. Ask the user to attach the file. Read it fully: `pdftotext -layout` for PDF (render pages to images if the text comes out garbled or is a scan), `pandoc` or python-docx for DOCX. Two-column CVs often extract out of order; check the page images and rebuild the reading order.
2. Extract into the profile structure: contact, roles (title, employer, dates, bullets), skills, education, certifications, languages, links.
3. Separate facts from claims:
   - Every number found goes to "Confirmed numbers" **only after the user confirms it** in step 3.
   - Skills only listed in a keyword block, with no role or project behind them, are marked "to confirm".
   - Merged roles at one employer ("Consultant → Senior → Lead") are split into separate roles with their own dates; ask for dates you cannot read.
4. Then run a **short gap interview** (step 2B, only the missing parts): target roles and locations, excluded employers, known gaps, writing voice, privacy rules. A CV never contains these.

## 2B. Interview
Ask in small groups, multiple-choice where it helps, and summarise after each group:
1. Contact details exactly as they should appear on a CV.
2. Targets: role titles, countries and work modes, excluded countries and employers, accepted working languages, availability, minimum match score (default 70%).
3. Roles, newest first: title, employer, dates, 2–5 achievements each. Separate titles at one employer stay separate.
4. Numbers: for each achievement without a figure, offer ranges ("about 10–20%? 20–40%? more?"). Store the low end with "around", "up to" or "+". If the user cannot give one, keep the bullet without a number. Never propose a number yourself.
5. Skills they truly have, then known gaps (things often asked for that they do not have).
6. Education, certifications with dates, languages with levels.
7. Writing voice: one message they wrote themselves.
8. Privacy rules: what must never appear on a CV or be told to recruiters.

## 2C. By hand
1. Send `templates/career-profile.example.md` as a file and explain: replace every `{{...}}`, delete sections that do not apply, keep one fact per line.
2. When the user sends it back, read it, list every remaining `{{`, empty section or unclear line, and ask only about those.
3. Generate `cv_base.json` from it (step 4).

## 3. Confirm
Show the finished profile in the chat (or as a file if long) with three short lists:
- **Numbers to confirm**: every figure, with the role it belongs to.
- **Skills to confirm**: anything marked "to confirm".
- **Open points**: anything still missing.
Update the profile with the answers. Only confirmed numbers stay in "Confirmed numbers".

## 4. Write the files
- `career-profile.md` in the structure of `templates/career-profile.example.md`, with no `{{` left.
- `cv_base.json` in the format of `templates/cv_base.example.json`, built only from the profile.
- Test the base CV: run `node scripts/ats_cv_generator.js cv_base.json base.docx`, convert to PDF, check with `pdftotext` that the contact details are at the top and it is at most 2 pages, and show it to the user as the neutral base CV.
- Save both files where the user keeps their job-search files: a Claude project, a connected folder, or sent to them as files. Say where they are.

## 5. Rules
- Only facts the user stated or that are in their own documents.
- Dates and titles exactly as given; never "improve" a job title.
- The original upload is never edited; work on a copy.
- Keep the profile under about 2 pages: every other skill reads it on every task.
