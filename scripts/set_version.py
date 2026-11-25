#!/usr/bin/env python3
"""Set an edition's version everywhere it appears, or check that all references agree.

    python scripts/set_version.py free 0.2.1     # before tagging free-v0.2.1
    python scripts/set_version.py pro 0.3.0      # before tagging pro-v0.3.0
    python scripts/set_version.py --check        # CI: every reference matches editions/*/plugin.json

Updates editions/<edition>/plugin.json, .claude-plugin/marketplace.json, the README download links,
and for the Free edition the engine's version and install commands. Then rebuilds plugins/.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = r"\d+\.\d+\.\d+"
# Files that mention "<edition>-vX.Y.Z" tags or "job-hunter-<edition>-X.Y.Z" asset names.
TEXT_FILES = {
    "pro": ["README.md"],
    "free": ["README.md", "engine/README.md", "editions/free/skills/setup-engine/SKILL.md",
             "engine/src/job_hunter_engine/cli.py"],
}
ENGINE_FILES = {
    "engine/pyproject.toml": re.compile(rf'^(version = ")({SEMVER})(")', re.M),
    "engine/src/job_hunter_engine/__init__.py": re.compile(rf'^(__version__ = ")({SEMVER})(")', re.M),
}


def patterns(edition: str) -> list[re.Pattern[str]]:
    return [
        re.compile(rf"({edition}-v)({SEMVER})"),
        re.compile(rf"(job-hunter-{edition}-(?:skills-)?)({SEMVER})"),
        re.compile(rf"(job_hunter_engine-)({SEMVER})") if edition == "free" else re.compile(r"(?!x)x"),
    ]


def plugin_version(edition: str) -> str:
    return json.loads((ROOT / "editions" / edition / "plugin.json").read_text(encoding="utf-8"))["version"]


def check() -> int:
    problems = []
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    by_name = {p["name"]: p["version"] for p in market["plugins"]}
    for edition in ("pro", "free"):
        version = plugin_version(edition)
        if by_name.get(f"job-hunter-{edition}") != version:
            problems.append(f"marketplace.json job-hunter-{edition} is {by_name.get(f'job-hunter-{edition}')}, plugin.json is {version}")
        for rel in TEXT_FILES[edition]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            for pat in patterns(edition):
                for m in pat.finditer(text):
                    if m.group(2) != version:
                        problems.append(f"{rel}: '{m.group(0)}' should be {version}")
        if edition == "free":
            for rel, pat in ENGINE_FILES.items():
                m = pat.search((ROOT / rel).read_text(encoding="utf-8"))
                if not m or m.group(2) != version:
                    problems.append(f"{rel}: engine version should be {version}")
    if problems:
        print("Version references disagree:\n  " + "\n  ".join(problems))
        return 1
    print("Version references agree.")
    return 0


def set_version(edition: str, version: str) -> None:
    path = ROOT / "editions" / edition / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    mpath = ROOT / ".claude-plugin/marketplace.json"
    market = json.loads(mpath.read_text(encoding="utf-8"))
    for plugin in market["plugins"]:
        if plugin["name"] == f"job-hunter-{edition}":
            plugin["version"] = version
    versions = sorted((tuple(map(int, p["version"].split("."))) for p in market["plugins"]), reverse=True)
    market["metadata"]["version"] = ".".join(map(str, versions[0]))
    mpath.write_text(json.dumps(market, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for rel in TEXT_FILES[edition]:
        p = ROOT / rel
        text = p.read_text(encoding="utf-8")
        for pat in patterns(edition):
            text = pat.sub(lambda m: m.group(1) + version, text)
        p.write_text(text, encoding="utf-8")
    if edition == "free":
        for rel, pat in ENGINE_FILES.items():
            p = ROOT / rel
            p.write_text(pat.sub(lambda m: m.group(1) + version + m.group(3), p.read_text(encoding="utf-8")), encoding="utf-8")

    subprocess.run([sys.executable, str(ROOT / "scripts/build_editions.py")], check=True)
    print(f"{edition} is now {version}. Add a '## {edition.capitalize()} {version}' section to CHANGELOG.md, "
          f"commit, merge, then tag: git tag {edition}-v{version} && git push origin {edition}-v{version}")


def main(argv: list[str]) -> int:
    if argv == ["--check"]:
        return check()
    if len(argv) != 2 or argv[0] not in ("pro", "free") or not re.fullmatch(SEMVER, argv[1]):
        print(__doc__)
        return 2
    set_version(argv[0], argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
