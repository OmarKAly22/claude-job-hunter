---
name: cv-job-tailoring
description: Tailor the user's CV to a job posting. Read the posting, score the fit honestly against career-profile.md, build an ATS-safe one-column PDF CV only when the match reaches the threshold, and draft any application email, cover note or form answer in the user's own voice.
---

# CV job tailoring

Use this whenever the user shares a job posting (link, pasted text or file) and asks to fit, compare or create a CV, or to draft an application email, cover letter, hiring-manager message or form answers.

**Source of facts:** `career-profile.md` (run `setup-profile` first if it does not exist) and anything the user states in the conversation. Nothing else.

## 1. Get the full posting
- Pasted text or a file: read it directly.
- Normal pages: fetch them. JavaScript job boards (Greenhouse, Ashby, Workday, Eightfold) often come back empty: open them in a browser and read the page text, or, without a browser, ask the user to paste the posting text.
- A job from the local engine's leads file (Free edition) already carries its full description: use it.
- LinkedIn search URLs show whichever job is selected; open `https://www.linkedin.com/jobs/view/<jobId>/` instead.
- Confirm the posting you read is the one the user meant.

## 2. Prove the link is live (before scoring a job from a list)
- Open the exact URL in a real browser and read the final URL, page title and first lines. It must show that single job with the same title.
- A fetch or search result is NOT proof; it can return an old cached copy of a closed job.
- Dead signs: 404, "job not found", "no longer available", "position filled", "expired", "nicht mehr verfügbar", "Bereits vergeben", a redirect to a job list or careers home page, a different job title.
- Without a browser in Claude, the local Job Hunter engine can check it: call its `verify_job_links` tool if it is connected, or ask the user to run `job-hunter verify <url>` and paste the result.
- A job from the engine's leads file counts as live when its `link_checked` is today or yesterday (its `verification` and `link_proof` say how).
- If neither a browser nor the engine is available, say the link is unconfirmed instead of calling it live, and ask the user to open it before applying.

## 3. Match score (always first, before building anything)
1. List every requirement and label it must-have or nice-to-have.
2. Score each against the profile only: **1.0** clearly evidenced, **0.5** partial or transferable (e.g. AWS when GCP is asked, or a language one level below what is asked), **0** not evidenced or a known gap.
3. Weights: must-have 3, nice-to-have 1. Match % = Σ(weight × score) / Σ(weights) × 100, rounded to the nearest 5.
4. Adjustments: hard blocker the user cannot meet (residence or contract restricted to a country, a required licence or degree, a language they lack) → cap at 50% and name it. Seniority mismatch → minus 10. Warning signs (commission-only pay, "recruit new members") → do not score; say it is not a real job.
5. Show a table: Requirement | Must/Nice | Score | Evidence. Then "Match: X%", top 3 strengths, top 3 gaps.

**Decision:** at or above the profile's threshold (default 70%) → build the CV. Below → do not build; explain the missing must-haves and suggest which roles fit better. Build anyway only if the user explicitly insists, and say again that it is a stretch. In job lists, never show roles below the threshold.

## 4. Honesty rules (non-negotiable)
- Never invent metrics, roles, tools or achievements, even if asked.
- Use only the profile's "Confirmed numbers". If the posting values a metric the user has not given, ask with ranges; never fill it in yourself.
- Never claim anything under "Known gaps"; list those as gaps in the delivery message.
- After each CV, list anything you reworded beyond the user's own words so they can confirm it.
- Follow the profile's privacy rules (e.g. no citizenship, no internal project names).

## 5. Build the CV (ATS-safe, mandatory layout)
Applicant tracking systems read top to bottom; sidebars, tables and text boxes get mixed into the job history.
- One single column. No tables, text boxes, columns, shapes, icons, photos, charts or skill bars.
- Name, headline and contact details as normal text at the top of the body, never in a Word header or footer.
- Sections in this order: Professional Summary, Skills, Professional Experience, Projects and Publications (optional), Education, Certifications, Languages.
- Each job: "Title | Company" with dates right-aligned, then real bullets. Separate titles at one employer stay separate.
- Arial 10 pt body, 11 pt headings, 16 pt name, black, A4 or Letter, two pages maximum.
- **Build:** fill a JSON in the format of `templates/cv_base.example.json` and run `node scripts/ats_cv_generator.js data.json out.docx` (needs `npm install docx`), then convert with `soffice --headless --convert-to pdf out.docx`. For a posting in another language, translate the content and set `labels`.

**What to tailor:** headline (the posting's title or the closest honest title), a two-paragraph summary with the 2–3 most relevant confirmed numbers, the order of the skills lines, and the order and wording of bullets, using the posting's own words wherever they are true.

**Keyword pass:** list the posting's keywords. Use the exact spelling of each one the user truly has in Skills and at least once in a bullet or the summary; spell acronyms out once. Never add a gap keyword.

**Numbers:** at least 3 bullets of the current role carry a confirmed number. Lead bullets with the result where possible.

## 6. Check before delivery (every time, also after small edits)
Run `pdftotext` on the PDF and check:
1. Name and every contact detail at the top of page 1.
2. Headline and file name match this company and role; no leftover company from an earlier CV.
3. Titles, employers and dates match the profile.
4. No placeholders: no `[`, `{{`, TODO or duplicated lines.
5. Every number is in the profile's confirmed list.
6. Languages, degrees and certifications are correct.
7. Two pages maximum; the .docx contains no `<w:tbl>`, `<w:drawing>` or `<w:txbxContent>`.
8. Reading order: each job line is directly followed by its own bullets.
9. Keyword coverage: report how many posting keywords matched and which must-haves are missing.

## 7. Deliver
- PDF only, named `<Name>_CV_<Company>_<Role>.pdf`.
- Start the reply with the match %, then one line on keyword coverage and one line saying the check passed.
- Mention knockout questions in the posting (work permit, location, mandatory skills): a format cannot get past those.
- If a form field has a character limit, fit the text to it and state the count.

## 8. Messages in the user's voice
For hiring-manager notes, cover notes and form answers, follow the profile's "Writing voice": their greeting and sign-off, plain first-person sentences, one concrete proof, then one line on what they would help the company achieve and their availability. Three short paragraphs at most, no buzzwords, no flattery. Never send anything; give the text to the user.

## 9. Comparing CV versions
Extract the text of both (`pdftotext -layout`), report differences as wording, structure, and added or removed content, and run the check in section 6 on both.
