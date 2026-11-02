#!/usr/bin/env python3
"""Experience catalog, explicit capture, lint and retirement. Python stdlib only."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SECTIONS = ("Symptoms", "Failed Approach", "Root Cause", "Verified Resolution", "Applicability", "Evidence")
FIELDS = {"name", "description", "status", "tags"}
MAX_BYTES = 16384


class ExperienceError(ValueError):
    pass


def root(value: str | None) -> Path:
    start = Path(value or os.getcwd()).expanduser().resolve()
    if value:
        return start
    for directory in (start, *start.parents):
        if (directory / ".git").exists() or (directory / "AGENTS.md").is_file():
            return directory
    return start


def folders(repo: Path, scope: str) -> list[Path]:
    home = Path(os.environ.get("AGENTS_HOME", str(Path.home() / ".agents"))).expanduser()
    return ([home / "experiences"] if scope in ("both", "global") else []) + (
        [repo / ".agents" / "experiences"] if scope in ("both", "project") else [])


def parse(path: Path) -> dict[str, str]:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ExperienceError(f"{path}: file missing or larger than {MAX_BYTES} bytes")
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise ExperienceError(f"{path}: missing frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ExperienceError(f"{path}: unclosed frontmatter") from exc
    metadata: dict[str, str] = {}
    for line in lines[1:closing]:
        key, sep, value = line.partition(":")
        if not sep or key not in FIELDS or key in metadata or not value.strip():
            raise ExperienceError(f"{path}: invalid metadata line: {line!r}")
        metadata[key] = value.strip()
    if set(metadata) != FIELDS or not SLUG.fullmatch(metadata["name"]):
        raise ExperienceError(f"{path}: requires name/description/status/tags and slug name")
    if metadata["name"] != path.stem or len(metadata["description"]) > 240:
        raise ExperienceError(f"{path}: invalid filename or description length")
    if metadata["status"] not in ("active", "retired"):
        raise ExperienceError(f"{path}: status must be active or retired")
    body = "\n".join(lines[closing + 1:])
    for heading in SECTIONS:
        match = re.search(rf"(?ms)^## {heading}\s*\n(.*?)(?=^## |\Z)", body)
        if match is None or not match.group(1).strip():
            raise ExperienceError(f"{path}: missing or empty section {heading}")
    return metadata


def catalog(repo: Path, scope: str, strict: bool = False) -> list[dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for folder in folders(repo, scope):
        for path in sorted(folder.glob("*.md")):
            try:
                meta = parse(path)
                index[meta["name"]] = {**meta, "path": str(path)}
            except (ExperienceError, OSError, UnicodeError) as exc:
                errors.append(str(exc))
    if errors and strict:
        raise ExperienceError("\n".join(errors))
    for message in errors:
        print("warning: " + message, file=sys.stderr)
    return list(index.values())


def relevance(meta: dict[str, str], query: str) -> int:
    if not query.strip():
        return 1
    words = set(re.findall(r"\w+", query.casefold()))
    name = meta["name"].replace("-", " ").casefold()
    tags = meta["tags"].replace(",", " ").casefold()
    description = meta["description"].casefold()
    return sum(4 * (word in name) + 2 * (word in tags) + (word in description)
               for word in words)


def list_cmd(args: argparse.Namespace, repo: Path) -> None:
    ranked = sorted(
        ((relevance(m, args.query), m) for m in catalog(repo, args.scope)
         if m["status"] == "active"),
        key=lambda pair: (-pair[0], pair[1]["name"]))
    selected = [m for value, m in ranked if value > 0][:args.limit]
    if args.json:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    else:
        for m in selected:
            print(f'{m["name"]}: {m["description"]} [{m["path"]}]')


def show_cmd(args: argparse.Namespace, repo: Path) -> None:
    meta = next((m for m in catalog(repo, args.scope, strict=True)
                 if m["name"] == args.name and m["status"] == "active"), None)
    if meta is None:
        raise ExperienceError(f"active experience not found: {args.name}")
    print(Path(meta["path"]).read_text(encoding="utf-8"))


def capture_cmd(args: argparse.Namespace, repo: Path) -> None:
    if not args.verified:
        raise ExperienceError("capture requires --verified after confirming the fix")
    if not SLUG.fullmatch(args.name) or not 1 <= len(args.description) <= 240:
        raise ExperienceError("invalid slug or description")
    if any("\n" in x or "\r" in x for x in (args.description, args.tags)):
        raise ExperienceError("metadata must be single-line")
    values = [args.symptoms, args.failed_approach, args.root_cause,
              args.resolution, args.applicability, args.evidence]
    if any(not x.strip() for x in values):
        raise ExperienceError("all experience sections must be nonempty")
    folder = folders(repo, args.scope)[0]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (args.name + ".md")
    lines = ["---", f"name: {args.name}", f"description: {args.description}",
             "status: active", f"tags: {args.tags}", "---", "", f"# {args.name}", ""]
    for heading, value in zip(SECTIONS, values):
        lines.extend((f"## {heading}", value.strip(), ""))
    content = "\n".join(lines)
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise ExperienceError("experience too large")
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise ExperienceError(f"already exists: {path}; merge manually") from exc
    try:
        parse(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    print(path)


def retire_cmd(args: argparse.Namespace, repo: Path) -> None:
    meta = next((m for m in catalog(repo, args.scope, strict=True)
                 if m["name"] == args.name), None)
    if meta is None:
        raise ExperienceError(f"experience not found: {args.name}")
    if meta["status"] == "retired":
        return
    path = Path(meta["path"])
    content = path.read_text(encoding="utf-8")
    path.write_text(content.replace("\nstatus: active\n", "\nstatus: retired\n", 1),
                    encoding="utf-8")
    print(f"retired: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="repo root; defaults to nearest .git or AGENTS.md")
    sub = parser.add_subparsers(dest="action", required=True)
    for command in ("list", "show", "capture", "retire", "lint"):
        item = sub.add_parser(command)
        item.add_argument("--scope", choices=("both", "project", "global"),
                          default="project" if command == "capture" else "both")
        if command in ("show", "retire"):
            item.add_argument("name")
        if command == "list":
            item.add_argument("--query", default="")
            item.add_argument("--limit", type=int, default=12)
            item.add_argument("--json", action="store_true")
        if command == "capture":
            for name in ("name", "description", "symptoms", "failed-approach", "root-cause",
                         "resolution", "applicability", "evidence"):
                item.add_argument("--" + name, required=True)
            item.add_argument("--tags", default="general")
            item.add_argument("--verified", action="store_true")
    args = parser.parse_args()
    try:
        repo = root(args.repo)
        if args.action == "list":
            if args.limit < 1:
                raise ExperienceError("--limit must be positive")
            list_cmd(args, repo)
        elif args.action == "show":
            show_cmd(args, repo)
        elif args.action == "capture":
            if args.scope == "both":
                raise ExperienceError("capture requires explicit project or global scope")
            capture_cmd(args, repo)
        elif args.action == "retire":
            retire_cmd(args, repo)
        else:
            print(f"validated {len(catalog(repo, args.scope, strict=True))} experiences")
        return 0
    except (ExperienceError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
