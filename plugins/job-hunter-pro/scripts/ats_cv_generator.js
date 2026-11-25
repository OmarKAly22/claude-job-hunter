// ATS-safe CV generator: single column, real text, standard headings,
// contact details in the body (never in header/footer), no tables, icons or images.
// Usage: npm install docx && node ats_cv_generator.js data.json out.docx
// Then:  soffice --headless --convert-to pdf out.docx
// Optional "labels" in the JSON translate section headings (e.g. German CVs).
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, LevelFormat,
  BorderStyle, TabStopType,
} = require("docx");

const d = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const L = Object.assign({
  summary: "Professional Summary", skills: "Skills", exp: "Professional Experience",
  proj: "Projects and Publications", edu: "Education", certs: "Certifications", lang: "Languages",
}, d.labels || {});
const FONT = "Arial";
const INK = "1A1A1A";
const RIGHT = 10466; // A4 text width with 0.5in margins (DXA)

const t = (text, o = {}) => new TextRun({ text, font: FONT, size: o.size || 20, bold: o.bold, italics: o.italics, color: o.color || INK });
const p = (children, o = {}) => new Paragraph({ children, spacing: { before: o.before || 0, after: o.after ?? 40, line: o.line || 264 }, alignment: o.align, tabStops: o.tabs, keepNext: o.keepNext, border: o.border });
const heading = (txt) => p([t(txt.toUpperCase(), { bold: true, size: 22 })], {
  before: 160, after: 60, keepNext: true,
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "555555", space: 2 } },
});
const bullet = (txt) => new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 30, line: 264 }, children: [t(txt)] });
const roleLine = (left, right) => p([t(left, { bold: true }), t("\t" + right)], { before: 80, after: 10, keepNext: true, tabs: [{ type: TabStopType.RIGHT, position: RIGHT }] });

const kids = [];
kids.push(p([t(d.name, { bold: true, size: 32 })], { after: 20 }));
kids.push(p([t(d.headline, { bold: true, size: 22 })], { after: 30 }));
kids.push(p([t(d.contact.join("  |  "), { size: 19 })], { after: 20 }));
if (d.contact2 && d.contact2.length) kids.push(p([t(d.contact2.join("  |  "), { size: 19 })], { after: 40 }));

kids.push(heading(L.summary));
d.summary.forEach(s => kids.push(p([t(s)], { after: 50 })));

kids.push(heading(L.skills));
d.skills.forEach(([k, v]) => kids.push(p([t(k + ": ", { bold: true }), t(v)], { after: 30 })));

kids.push(heading(L.exp));
d.experience.forEach(j => {
  kids.push(roleLine(`${j.title} | ${j.company}`, j.dates));
  if (j.sub) kids.push(p([t(j.sub, { italics: true, size: 19 })], { after: 30, keepNext: true }));
  j.bullets.forEach(b => kids.push(bullet(b)));
});

if (d.projects && d.projects.length) { kids.push(heading(L.proj)); d.projects.forEach(b => kids.push(bullet(b))); }

kids.push(heading(L.edu));
d.education.forEach(e => kids.push(roleLine(e[0], e[1]), p([t(e[2] || "", { size: 19 })], { after: 30 })));

if (d.certs && d.certs.length) { kids.push(heading(L.certs)); d.certs.forEach(c => kids.push(bullet(c))); }

kids.push(heading(L.lang));
kids.push(p([t(d.languages)]));

if (d.extra) { kids.push(heading(d.extra.title)); d.extra.items.forEach(b => kids.push(bullet(b))); }

const doc = new Document({
  creator: d.name, title: `${d.name} – CV`,
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  numbering: { config: [{ reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 300, hanging: 220 } } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 720, bottom: 720, left: 720, right: 720 } } }, children: kids }],
});
Packer.toBuffer(doc).then(b => fs.writeFileSync(process.argv[3], b));
