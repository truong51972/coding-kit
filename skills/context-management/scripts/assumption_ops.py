#!/usr/bin/env python3
"""Optional, project-local Markdown assumption ledger (stdlib only).

No ledger is created by skill installation or context init. Capturing a
provisional assumption never promotes it into a durable context fact.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

ENTRY = re.compile(r"(?m)^- \[([ x])\] (ASM-\d{3,}) \| (.+)$")
FIELDS = ("Status", "Scope", "Decision affected", "Basis", "Verify by", "Owner")
STATES = {"provisional", "verified", "rejected", "retired"}
HEADER = "# Assumption Ledger\n\n"
MAX_BYTES = 64 * 1024


class LedgerError(ValueError):
    pass


def _target(repo: Path, value: str | None) -> Path:
    root = repo.resolve()
    path = (root / (value or ".agents/assumptions/ledger.md")).resolve()
    if not path.is_relative_to(root):
        raise LedgerError("ledger must remain inside the project")
    rel = path.relative_to(root).as_posix()
    if rel == "AGENTS.md" or rel.startswith(".agents/contexts/") or rel.startswith(".agents/experiences/"):
        raise LedgerError("provisional ledger cannot overwrite contexts, experiences or AGENTS.md")
    if path.suffix != ".md":
        raise LedgerError("ledger must be a Markdown file")
    return path


def _load(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LedgerError("ledger missing; run init explicitly or use a task artifact") from exc
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise LedgerError("ledger exceeds 64 KiB; review and split it by domain")
    return content


def _parse(content: str) -> list[dict[str, str | int]]:
    if not content.startswith(HEADER):
        raise LedgerError("expected '# Assumption Ledger' header")
    matches = list(ENTRY.finditer(content))
    items: list[dict[str, str | int]] = []
    seen: set[str] = set()
    if not matches and content.strip() != HEADER.strip():
        raise LedgerError("unrecognized ledger content")
    for i, match in enumerate(matches):
        entry = content[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(content)]
        details: dict[str, str] = {}
        for line in entry.strip().splitlines():
            if not line.strip():
                continue
            meta = re.fullmatch(r"  - ([A-Za-z ]+): (.+)", line)
            if not meta or meta.group(1) in details:
                raise LedgerError(f"{match.group(2)}: invalid or duplicated metadata")
            details[meta.group(1)] = meta.group(2).strip()
        if not all(details.get(key) for key in FIELDS):
            raise LedgerError(f"{match.group(2)}: missing required metadata")
        state = details["Status"]
        if state not in STATES or (match.group(1) == "x") != (state != "provisional"):
            raise LedgerError(f"{match.group(2)}: invalid status or checkbox")
        if state in {"verified", "rejected"} and not details.get("Evidence"):
            raise LedgerError(f"{match.group(2)}: verified/rejected requires evidence")
        if match.group(2) in seen:
            raise LedgerError(f"{match.group(2)}: duplicate identity")
        seen.add(match.group(2))
        items.append({"id": match.group(2), "claim": match.group(3).strip(),
                      "state": state, "start": match.start(), "end": matches[i + 1].start()
                      if i + 1 < len(matches) else len(content), **details})
    return items


def _safe_text(value: str) -> str:
    if not value.strip() or "\n" in value or "\r" in value:
        raise LedgerError("metadata must be one non-empty line")
    return value.strip()


def _render(ident: str, claim: str, details: dict[str, str]) -> str:
    checkbox = " " if details["Status"] == "provisional" else "x"
    return (f"- [{checkbox}] {ident} | {claim}\n" +
            "".join(f"  - {key}: {value}\n" for key, value in details.items()) + "\n")


def _write(path: Path, content: str) -> None:
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise LedgerError("ledger exceeds 64 KiB")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".assumptions-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Manage optional Markdown assumptions")
    p.add_argument("--repo", default=".")
    p.add_argument("--ledger", help="explicit project-owned Markdown file")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("lint")
    sub.add_parser("list").add_argument("--query", default="")
    sub.add_parser("show").add_argument("id")
    capture = sub.add_parser("capture")
    capture.add_argument("--id")
    for flag in ("claim", "scope", "decision", "basis", "verify-by", "owner"):
        capture.add_argument("--" + flag, required=True)
    resolve = sub.add_parser("resolve")
    resolve.add_argument("id")
    resolve.add_argument("--status", required=True, choices=("verified", "rejected", "retired"))
    resolve.add_argument("--evidence")
    resolve.add_argument("--successor")
    args = p.parse_args(argv)
    try:
        path = _target(Path(args.repo), args.ledger)
        if args.command == "init":
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open("x", encoding="utf-8") as f:
                    f.write(HEADER)
            except FileExistsError:
                _parse(_load(path))
                print(f"already initialized: {path}")
                return 0
            print(f"created: {path}")
            return 0
        content = _load(path)
        entries = _parse(content)
        if args.command == "lint":
            print(f"valid: {len(entries)} assumptions")
        elif args.command == "list":
            for item in entries:
                if args.query.casefold() in f"{item['id']} {item['claim']} {item['Scope']}".casefold():
                    print(f"{item['id']}: {item['state']}: {item['claim']} [{item['Scope']}]")
        elif args.command == "show":
            entry = next((e for e in entries if e["id"] == args.id), None)
            if entry is None:
                raise LedgerError("assumption not found")
            print(content[int(entry["start"]):int(entry["end"])].strip())
        elif args.command == "capture":
            claim = _safe_text(args.claim)
            scope = _safe_text(args.scope)
            same = next((e for e in entries if e["claim"].casefold() == claim.casefold()
                         and e["Scope"].casefold() == scope.casefold()), None)
            if same:
                print(f"existing: {same['id']} (use the canonical record)")
                return 0
            ident = args.id or f"ASM-{max([int(str(e['id']).split('-')[1]) for e in entries] + [0]) + 1:03d}"
            if not re.fullmatch(r"ASM-\d{3,}", ident) or any(e["id"] == ident for e in entries):
                raise LedgerError("invalid or duplicate assumption ID")
            details = {"Status": "provisional", "Scope": scope,
                       "Decision affected": _safe_text(args.decision),
                       "Basis": _safe_text(args.basis),
                       "Verify by": _safe_text(args.verify_by),
                       "Owner": _safe_text(args.owner)}
            new = content.rstrip() + "\n\n" + _render(ident, claim, details)
            _parse(new)
            _write(path, new)
            print(f"captured: {ident}")
        elif args.command == "resolve":
            item = next((e for e in entries if e["id"] == args.id), None)
            if item is None:
                raise LedgerError("assumption not found")
            if args.status in {"verified", "rejected"} and not args.evidence:
                raise LedgerError("verified/rejected requires --evidence")
            if item["state"] != "provisional":
                if item["state"] == args.status and (
                    not args.evidence or item.get("Evidence") == args.evidence):
                    print(f"unchanged: {args.id}")
                    return 0
                raise LedgerError("resolved assumption is immutable; add a new scoped record")
            details = {key: str(item[key]) for key in FIELDS}
            details["Status"] = args.status
            if args.evidence:
                details["Evidence"] = _safe_text(args.evidence)
            if args.successor:
                details["Successor"] = _safe_text(args.successor)
            # Keep a stable field order and update the current record rather than append history.
            updated = _render(args.id, str(item["claim"]), details)
            new = content[:int(item["start"])] + updated + content[int(item["end"]):]
            _parse(new)
            _write(path, new)
            print(f"resolved: {args.id}: {args.status}")
        return 0
    except (LedgerError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
