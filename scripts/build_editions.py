#!/usr/bin/env python3
"""Assemble the Pro and Free plugins from shared/ and editions/.

    python scripts/build_editions.py            # rebuild plugins/job-hunter-pro and plugins/job-hunter-free
    python scripts/build_editions.py --check    # fail if plugins/ is out of date (used in CI)
    python scripts/build_editions.py --zip pro  # also write dist/job-hunter-pro-<version>.zip

Never edit plugins/ by hand: change shared/ (both editions) or editions/<edition>/ (one edition).
An edition file with the same path as a shared file replaces it.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITIONS = ("pro", "free")
SKIP = {".DS_Store", "node_modules", "__pycache__"}
# Files copied from elsewhere in the repo into one edition (source → path inside the plugin).
EXTRA_FILES = {
    "free": [("engine/src/job_hunter_engine/config.example.toml", "templates/engine-config.example.toml")],
}


def _copytree(src: Path, dst: Path) -> None:
    for path in sorted(src.rglob("*")):
        if any(part in SKIP for part in path.parts):
            continue
        target = dst / path.relative_to(src)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def build(edition: str, out_root: Path) -> Path:
    edition_dir = ROOT / "editions" / edition
    manifest = json.loads((edition_dir / "plugin.json").read_text(encoding="utf-8"))
    out = out_root / manifest["name"]
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    _copytree(ROOT / "shared", out)
    for item in edition_dir.iterdir():
        if item.name == "plugin.json":
            continue
        if item.is_dir():
            _copytree(item, out / item.name)
        else:
            shutil.copy2(item, out / item.name)
    for src, dst in EXTRA_FILES.get(edition, []):
        (out / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / src, out / dst)
    (out / ".claude-plugin").mkdir(exist_ok=True)
    shutil.copy2(edition_dir / "plugin.json", out / ".claude-plugin" / "plugin.json")
    return out


def _same_tree(a: Path, b: Path) -> list[str]:
    diffs: list[str] = []
    cmp = filecmp.dircmp(a, b, ignore=list(SKIP))

    def walk(c: filecmp.dircmp, rel: Path) -> None:
        diffs.extend(str(rel / n) for n in c.left_only + c.right_only + c.diff_files + c.funny_files)
        for name, sub in c.subdirs.items():
            walk(sub, rel / name)

    walk(cmp, Path(a.name))
    return diffs


def zip_edition(plugin_dir: Path, dist: Path) -> Path:
    manifest = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    dist.mkdir(parents=True, exist_ok=True)
    target = dist / f"{manifest['name']}-{manifest['version']}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(plugin_dir.rglob("*")):
            if path.is_file() and not any(part in SKIP for part in path.parts):
                zf.write(path, Path(plugin_dir.name) / path.relative_to(plugin_dir))
    return target


def zip_skills_only(plugin_dir: Path, dist: Path) -> Path:
    """One zip per skill folder, bundled together, for accounts that can upload skills but not plugins."""
    manifest = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    dist.mkdir(parents=True, exist_ok=True)
    target = dist / f"{manifest['name']}-skills-{manifest['version']}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for skill in sorted((plugin_dir / "skills").iterdir()):
            if not skill.is_dir():
                continue
            with tempfile.TemporaryDirectory() as tmp:
                inner = Path(tmp) / f"{skill.name}.zip"
                with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as izf:
                    for path in sorted(skill.rglob("*")):
                        if path.is_file():
                            izf.write(path, Path(skill.name) / path.relative_to(skill))
                    # A skill uploaded on its own has no plugin around it: give it the shared
                    # scripts/ and templates/ so paths like templates/... still resolve.
                    for folder in ("scripts", "templates"):
                        for path in sorted((plugin_dir / folder).rglob("*")):
                            if path.is_file() and not any(part in SKIP for part in path.parts):
                                izf.write(path, Path(skill.name) / path.relative_to(plugin_dir))
                zf.write(inner, inner.name)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only check that plugins/ is up to date")
    parser.add_argument("--zip", choices=EDITIONS, action="append", default=[], help="write release zips to dist/")
    args = parser.parse_args()

    if args.check:
        problems: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            for edition in EDITIONS:
                built = build(edition, Path(tmp))
                committed = ROOT / "plugins" / built.name
                if not committed.exists():
                    problems.append(f"missing {committed.relative_to(ROOT)}")
                else:
                    problems.extend(_same_tree(built, committed))
        if problems:
            print("plugins/ is out of date. Run: python scripts/build_editions.py\n  " + "\n  ".join(problems))
            return 1
        print("plugins/ is up to date.")
        return 0

    for edition in EDITIONS:
        out = build(edition, ROOT / "plugins")
        print(f"built {out.relative_to(ROOT)}")
        if edition in args.zip:
            print(f"  zip    {zip_edition(out, ROOT / 'dist').relative_to(ROOT)}")
            print(f"  skills {zip_skills_only(out, ROOT / 'dist').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
