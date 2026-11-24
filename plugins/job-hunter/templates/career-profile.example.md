# Career profile

The only source of facts for your CVs, match scores and messages. Claude never adds anything that is not written here or that you did not say in the conversation. Run the `setup-profile` skill to fill this in through a short interview, or edit it by hand.

## Contact (printed at the top of every CV)
- Name: {{FULL_NAME}}
- Email: {{EMAIL}}
- Phone: {{PHONE}}
- LinkedIn: {{LINKEDIN_URL}}
- Other links (GitHub, blog, portfolio): {{LINKS}}
- City, country: {{CITY_COUNTRY}}

## Target
- Role titles I want: {{ROLE_TITLES}}
- Countries and work modes in scope: {{LOCATIONS}}  (e.g. "Germany on-site/hybrid; EU remote")
- Countries or regions excluded: {{EXCLUDED_LOCATIONS}}
- Employers excluded (current employer, its group, others): {{EXCLUDED_EMPLOYERS}}
- Working languages accepted: {{LANGUAGES_ACCEPTED}}
- Available from / notice period: {{AVAILABILITY}}
- Minimum match score to show a job: {{MIN_MATCH | default 70}}%
- Leads per day: minimum {{DAILY_MIN | default 10}}, maximum {{DAILY_MAX | default none}}

## Experience (newest first; one block per role, even at the same employer)
### {{TITLE}} | {{EMPLOYER}} | {{START}} – {{END}}
- {{WHAT YOU DID, with the result}}

## Confirmed numbers (the ONLY figures allowed on a CV)
- {{e.g. "Team of 6 engineers" / "~40% less manual effort on the data platform, 50+ users"}}
Each number belongs to one project. Claude never rounds up, merges or moves a number to another project.

## Skills I truly have
- Programming: {{...}}
- Cloud and infrastructure: {{...}}
- Data and AI: {{...}}
- Leadership and delivery: {{...}}

## Known gaps (never claimed, scored 0)
- {{e.g. Kubernetes, Azure, Java}}

## Education
- {{DEGREE}}, {{SCHOOL}} ({{YEARS}})

## Certifications
- {{NAME}}, {{ISSUER}} ({{DATE}}, valid to {{DATE}})

## Languages
- {{LANGUAGE}} {{LEVEL}}

## Writing voice (for messages and form answers)
- Greeting / sign-off: {{e.g. "Dear Hiring Manager," / "Sincerely,"}}
- A message I wrote myself that sounds like me: {{PASTE}}

## Privacy rules
- Never put on a CV: {{e.g. citizenship, date of birth, photo, salary}}
- Never mention to recruiters: {{e.g. my other interview processes}}
- Project or client names that must stay internal: {{...}}
