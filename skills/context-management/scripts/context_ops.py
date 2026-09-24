#!/usr/bin/env python3
"""Deterministic helpers for the context-management skill.

These checks intentionally do not verify semantic accuracy against repository
source files. Semantic verification is an agent workflow.
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse


SCHEMA_VERSION = 1
MANAGED_BLOCK_START = "<!-- context-management:start -->"
MANAGED_BLOCK_END = "<!-- context-management:end -->"
DEFAULT_FILES = (
    "source-priority.md",
    "project-baseline.md",
    "active-assumptions.md",
)
REQUIRED_MANAGED_HEADINGS = (
    ("##", "Context Management"),
    ("###", "Startup"),
    ("###", "Context Index"),
    ("###", "Project Working Conventions"),
)
LEGACY_CONTEXT_FILES = ("index.md", "working-conventions.md")

NOISE_PATTERNS = (
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bTBD\b",
    r"\bchangelog\b",
    r"\bsession summar(?:y|ies)\b",
    r"\bcompleted task",
    r"\bwhat just happened\b",
    r"\bwe (changed|fixed|added|removed|updated)\b",
    r"\bin this session\b",
    r"\blast session\b",
    r"\bjust (changed|fixed|added|removed|updated)\b",
    r"\bold version\b",
    r"\binstead of legacy\b",
)

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
SIGNATURE_RE = re.compile(r"\b(?:def|class)\s+[A-Za-z_][A-Za-z0-9_]*\s*(?:\(|:)")
SQL_DDL_RE = re.compile(r"\bCREATE\s+(?:TABLE|INDEX|VIEW)\b|\bALTER\s+TABLE\b", re.IGNORECASE)

SIZE_LIMITS = {
    "managed_warning_tokens": 1000,
    "managed_warning_lines": 100,
    "managed_strong_tokens": 2000,
    "shard_warning_tokens": 4000,
    "shard_warning_lines": 250,
    "shard_strong_tokens": 8000,
}

SEMANTIC_NOT_PERFORMED = {
    "status": "not_performed",
    "message": "Semantic verification requires the context-management agent workflow.",
}


@dataclass
class Finding:
    code: str
    severity: str
    file: str | None
    line: int | None
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "details": self.details,
        }


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def contexts_dir(repo: Path) -> Path:
    return repo / ".agents" / "contexts"


def agents_file(repo: Path) -> Path:
    return repo / "AGENTS.md"


def relpath(path: Path, repo: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def iter_markdown_files(root: Path) -> Iterable[Path]:
    if root.exists():
        yield from sorted(root.rglob("*.md"))


def estimated_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def strip_anchor(reference: str) -> str:
    return reference.split("#", 1)[0].strip().strip("<>")


def is_external_reference(value: str) -> bool:
    return value.startswith(("http://", "https://", "mailto:", "#"))


def markdown_references(text: str) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        reference = strip_anchor(match.group(1))
        if reference.endswith(".md") and not is_external_reference(reference):
            refs.append((reference, line_for_offset(text, match.start())))
    for match in CODE_SPAN_RE.finditer(text):
        reference = strip_anchor(match.group(1))
        if reference.endswith(".md") and not is_external_reference(reference):
            refs.append((reference, line_for_offset(text, match.start())))
    return refs


def markdown_link_references(text: str) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        reference = strip_anchor(match.group(1))
        if reference.endswith(".md") and not is_external_reference(reference):
            refs.append((reference, line_for_offset(text, match.start())))
    return refs


def managed_block(repo: Path) -> tuple[str | None, list[Finding]]:
    path = agents_file(repo)
    if not path.exists():
        return None, [
            Finding(
                "MANAGED_BLOCK_ERROR",
                "error",
                relpath(path, repo),
                None,
                "AGENTS.md is missing.",
            )
        ]

    text = read_text(path)
    starts = text.count(MANAGED_BLOCK_START)
    ends = text.count(MANAGED_BLOCK_END)
    if starts != 1 or ends != 1:
        return None, [
            Finding(
                "MANAGED_BLOCK_ERROR",
                "error",
                relpath(path, repo),
                None,
                "AGENTS.md must contain exactly one context-management marker pair.",
                {"starts": starts, "ends": ends},
            )
        ]

    start = text.index(MANAGED_BLOCK_START) + len(MANAGED_BLOCK_START)
    end = text.index(MANAGED_BLOCK_END)
    if end < start:
        return None, [
            Finding(
                "MANAGED_BLOCK_ERROR",
                "error",
                relpath(path, repo),
                None,
                "The context-management end marker precedes its start marker.",
            )
        ]

    block = text[start:end].strip()
    missing = [
        f"{level} {heading}"
        for level, heading in REQUIRED_MANAGED_HEADINGS
        if not re.search(rf"^{re.escape(level)}\s+{re.escape(heading)}\s*$", block, re.MULTILINE)
    ]
    if missing:
        return None, [
            Finding(
                "MANAGED_BLOCK_ERROR",
                "error",
                relpath(path, repo),
                None,
                "Managed context block is missing required headings.",
                {"missing_headings": missing},
            )
        ]
    return block, []


def managed_content_entries(repo: Path) -> list[tuple[Path, str]]:
    block, findings = managed_block(repo)
    if findings or block is None:
        return []
    entries = [(agents_file(repo), block)]
    entries.extend((path, read_text(path)) for path in iter_markdown_files(contexts_dir(repo)))
    return entries


def generic_managed_block() -> str:
    return read_text(template_dir() / "managed-block.md")


def insert_managed_block(text: str, block: str) -> str:
    match = re.search(r"^#\s+.+(?:\n|$)", text, re.MULTILINE)
    if not match:
        raise ValueError("AGENTS.md must contain an H1 before context initialization.")
    return text[: match.end()] + "\n" + block.rstrip() + "\n" + text[match.end() :]


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def resolve_context_reference(repo: Path, root: Path, reference: str) -> Path:
    path = Path(reference)
    if path.is_absolute():
        return path
    if path.parts[:2] == (".agents", "contexts"):
        return repo / path
    return root / path


def template_dir() -> Path:
    return skill_root() / "templates"


def init_context(repo: Path, overwrite: bool) -> int:
    repo = repo.resolve()
    target_dir = contexts_dir(repo)
    source_dir = template_dir()

    legacy_paths = [target_dir / name for name in LEGACY_CONTEXT_FILES if (target_dir / name).exists()]
    if legacy_paths:
        print("error: legacy context layout must be semantically migrated before init:")
        for path in legacy_paths:
            print(f"  {path}")
        return 2

    agents = agents_file(repo)
    if agents.exists():
        text = read_text(agents)
        starts = text.count(MANAGED_BLOCK_START)
        ends = text.count(MANAGED_BLOCK_END)
        if (starts, ends) != (0, 0):
            _block, findings = managed_block(repo)
            if findings:
                for finding in findings:
                    print(f"error: {finding.message}")
                return 2
        else:
            try:
                updated_agents = insert_managed_block(text, generic_managed_block())
            except ValueError as error:
                print(f"error: {error}")
                return 2
    else:
        updated_agents = "# Repository Instructions\n\n" + generic_managed_block().rstrip() + "\n"

    # All failure-prone preflight checks run before any write.
    if not agents.exists() or (starts, ends) == (0, 0):
        agents.parent.mkdir(parents=True, exist_ok=True)
        agents.write_text(updated_agents, encoding="utf-8")
        print(f"write {agents}")

    target_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0
    for name in DEFAULT_FILES:
        source = source_dir / name
        target = target_dir / name
        if target.exists() and not overwrite:
            print(f"skip existing {target}")
            skipped += 1
            continue
        shutil.copyfile(source, target)
        print(f"write {target}")
        created += 1

    legacy = repo / ".agents" / "context.md"
    if legacy.exists():
        print(f"legacy context found, not migrated automatically: {legacy}")

    print(f"done: {created} written, {skipped} skipped")
    return 0


def structural_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    root = contexts_dir(repo)
    findings: list[Finding] = []

    block, block_findings = managed_block(repo)
    findings.extend(block_findings)
    if block is None:
        return findings

    if not root.exists():
        findings.append(
            Finding(
                "STRUCTURE_ERROR",
                "error",
                relpath(root, repo),
                None,
                "Context directory is missing.",
            )
        )
        return findings

    for name in LEGACY_CONTEXT_FILES:
        legacy = root / name
        if legacy.exists():
            findings.append(
                Finding(
                    "LEGACY_LAYOUT_ERROR",
                    "error",
                    relpath(legacy, repo),
                    None,
                    "Legacy context layout file must be migrated or removed.",
                )
            )

    index_text = section_text(block, "Context Index")
    if not index_text:
        findings.append(
            Finding(
                "MANAGED_BLOCK_ERROR",
                "error",
                relpath(agents_file(repo), repo),
                None,
                "Managed context block requires a non-empty Context Index.",
            )
        )
        return findings

    seen_refs: dict[Path, list[tuple[str, int]]] = {}
    index_start = section_start_line(block, "Context Index")
    for reference, line in markdown_link_references(index_text):
        adjusted_line = line + index_start - 1
        target = resolve_context_reference(repo, root, reference)
        seen_refs.setdefault(target.resolve(), []).append((reference, adjusted_line))
        if escapes_repo(root, target):
            findings.append(
                Finding(
                    "CONTEXT_REFERENCE_ESCAPE",
                    "error",
                    relpath(agents_file(repo), repo),
                    adjusted_line,
                    f"Shard reference escapes context directory: {reference}.",
                    {"reference": reference, "resolved_to": relpath(target, repo)},
                )
            )
            continue

        if not target.exists():
            findings.append(
                Finding(
                    "BROKEN_REFERENCE",
                    "error",
                    relpath(agents_file(repo), repo),
                    adjusted_line,
                    f"Context Index references missing context file: {reference}.",
                    {"reference": reference, "resolved_to": relpath(target, repo)},
                )
            )

    for target, entries in sorted(seen_refs.items(), key=lambda item: str(item[0])):
        if len(entries) > 1:
            reference = entries[1][0]
            lines = [line for _reference, line in entries]
            findings.append(
                Finding(
                    "DUPLICATE_CONTENT_WARNING",
                    "warning",
                    relpath(agents_file(repo), repo),
                    lines[1],
                    f"Context Index references {reference} more than once.",
                    {
                        "reference": reference,
                        "lines": lines,
                        "resolved_to": relpath(target, repo),
                    },
                )
            )

    referenced_paths = {
        target
        for target in seen_refs
        if target.exists()
    }
    for path in iter_markdown_files(root):
        if path.name in LEGACY_CONTEXT_FILES:
            continue
        if path.resolve() not in referenced_paths:
            findings.append(
                Finding(
                    "ORPHAN_SHARD",
                    "warning",
                    relpath(path, repo),
                    None,
                    "Context shard is not referenced by the managed Context Index.",
                )
            )

    return findings


def lint_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    root = contexts_dir(repo)
    findings: list[Finding] = []
    block, block_findings = managed_block(repo)
    findings.extend(block_findings)
    if block is None or not root.exists():
        if not root.exists():
            findings.append(
                Finding(
                    "STRUCTURE_ERROR",
                    "error",
                    relpath(root, repo),
                    None,
                    "Context directory is missing.",
                )
            )
        return findings

    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in NOISE_PATTERNS]
    for path, text in managed_content_entries(repo):
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern in compiled:
                match = pattern.search(line)
                if match:
                    findings.append(
                        Finding(
                            "HYGIENE_WARNING",
                            "warning",
                            relpath(path, repo),
                            lineno,
                            f"Review possible session-history or changelog phrase: {match.group(0)}.",
                            {"line": line.strip()},
                        )
                    )
                    break
        findings.extend(source_detail_findings(path, repo, text))
    return findings


def source_detail_findings(path: Path, repo: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for match in FENCE_RE.finditer(text):
        body = match.group(1)
        line_count = len([line for line in body.splitlines() if line.strip()])
        if line_count >= 12:
            findings.append(
                Finding(
                    "POSSIBLE_SOURCE_DETAIL_DUPLICATION",
                    "warning",
                    relpath(path, repo),
                    line_for_offset(text, match.start()),
                    "Large code fence may duplicate source-owned detail.",
                    {"non_empty_lines": line_count},
                )
            )

    for pattern, label in (
        (SIGNATURE_RE, "function or class signature"),
        (SQL_DDL_RE, "SQL DDL"),
    ):
        for match in pattern.finditer(text):
            findings.append(
                Finding(
                    "POSSIBLE_SOURCE_DETAIL_DUPLICATION",
                    "warning",
                    relpath(path, repo),
                    line_for_offset(text, match.start()),
                    f"Context contains a {label}; verify this belongs in context.",
                    {"preview": match.group(0)[:120]},
                )
            )
    return findings


def identifier_density_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    root = contexts_dir(repo)
    findings: list[Finding] = []
    if not root.exists():
        return findings
    for path, text in managed_content_entries(repo):
        if path == agents_file(repo) or path.name == "source-priority.md":
            # These files legitimately concentrate exact paths and identifiers
            # for routing. Other checks still validate their links and paths.
            continue
        for heading, start_line, body in sections_by_heading(text):
            code_spans = [
                value.strip()
                for value in CODE_SPAN_RE.findall(body)
                if re.search(r"[A-Za-z0-9_/.-]", value)
            ]
            prose = CODE_SPAN_RE.sub("", body)
            exact_values = list(code_like_identifiers(prose)) + code_spans
            exact_chars = sum(len(value) for value in exact_values)
            density = exact_chars / max(len(body), 1)
            if len(exact_values) >= 12 and density >= 0.18:
                findings.append(
                    Finding(
                        "POSSIBLE_SOURCE_DETAIL_DUPLICATION",
                        "warning",
                        relpath(path, repo),
                        start_line,
                        "Section contains dense exact identifiers or code spans; verify it is not source-owned detail.",
                        {
                            "section": heading,
                            "identifier_count": len(exact_values),
                            "identifier_density": round(density, 3),
                            "preview": body.strip()[:160],
                        },
                    )
                )
    return findings


def code_like_identifiers(text: str) -> set[str]:
    values = set(
        re.findall(
            r"\b[A-Za-z][A-Za-z0-9_]*(?:[._/:-][A-Za-z0-9_*.-]+)+\b",
            text,
        )
    )
    values = {
        value
        for value in values
        if any(separator in value for separator in (".", "/", "_", ":"))
    }
    return {value for value in values if not value.startswith(("http://", "https://"))}


def lazy_loading_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    block, findings = managed_block(repo)
    if block is None:
        return []
    text = section_text(block, "Startup")
    checks = (
        (r"always\s+read\s+`?source-priority\.md`?", "Index eagerly requires source-priority.md."),
        (r"read\s+`?source-priority\.md`?\s+(?:before|for)\s+every\s+task", "Index requires source-priority.md for every task."),
        (r"read\s+all\s+context\s+files", "Index asks agents to read all context files."),
        (r"load\s+every\s+shard", "Index asks agents to load every shard."),
        (r"load\s+all\s+shards", "Index asks agents to load all shards."),
    )
    findings: list[Finding] = []
    for pattern, message in checks:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            findings.append(
                Finding(
                    "LAZY_LOADING_WARNING",
                    "warning",
                    relpath(agents_file(repo), repo),
                    section_start_line(block, "Startup") + line_for_offset(text, match.start()) - 1,
                    message.replace("Index", "Managed startup"),
                    {"matched": match.group(0)},
                )
            )
    return findings


def eager_shard_bundle_findings(repo: Path) -> list[Finding]:
    """Flag task routes that eagerly load multiple context shards."""
    repo = repo.resolve()
    block, findings = managed_block(repo)
    if block is None:
        return []
    policy = section_text(block, "Startup")
    if not policy:
        return []
    start = section_start_line(block, "Startup")
    findings: list[Finding] = []
    for offset, line in enumerate(policy.splitlines()):
        if not re.search(r"\b(?:load|read)\b", line, re.IGNORECASE):
            continue
        refs = {
            reference
            for reference, _line in markdown_references(line)
            if Path(reference).suffix.lower() == ".md"
        }
        if len(refs) < 2:
            continue
        findings.append(
                Finding(
                    "EAGER_SHARD_BUNDLE",
                    "warning",
                    relpath(agents_file(repo), repo),
                start + offset,
                "Loading policy eagerly bundles multiple shards for one task category.",
                {"references": sorted(refs), "line": line.strip()},
            )
        )
    return findings


def size_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    root = contexts_dir(repo)
    findings: list[Finding] = []
    block, _block_findings = managed_block(repo)
    if block is None or not root.exists():
        return findings

    entries = [(agents_file(repo), block)]
    entries.extend((path, read_text(path)) for path in iter_markdown_files(root))
    for path, text in entries:
        tokens = estimated_tokens(text)
        non_empty_lines = len([line for line in text.splitlines() if line.strip()])
        if path == agents_file(repo):
            if tokens > SIZE_LIMITS["managed_strong_tokens"]:
                message = "Managed context block exceeds the strong recommended token budget."
            elif (
                tokens > SIZE_LIMITS["managed_warning_tokens"]
                or non_empty_lines > SIZE_LIMITS["managed_warning_lines"]
            ):
                message = "Managed context block exceeds the recommended compactness budget."
            else:
                continue
            findings.append(
                Finding(
                    "SHARD_SIZE_WARNING",
                    "warning",
                    relpath(path, repo),
                    None,
                    message,
                    {
                        "estimated_tokens": tokens,
                        "non_empty_lines": non_empty_lines,
                    },
                )
            )
            continue

        if tokens > SIZE_LIMITS["shard_strong_tokens"]:
            message = "Shard exceeds the strong recommended token budget."
        elif (
            tokens > SIZE_LIMITS["shard_warning_tokens"]
            or non_empty_lines > SIZE_LIMITS["shard_warning_lines"]
        ):
            message = "Shard exceeds the recommended token or line budget."
        else:
            continue
        findings.append(
            Finding(
                "SHARD_SIZE_WARNING",
                "warning",
                relpath(path, repo),
                None,
                message,
                {"estimated_tokens": tokens, "non_empty_lines": non_empty_lines},
            )
        )

    return findings


def duplicate_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    root = contexts_dir(repo)
    if not root.exists():
        return []
    findings: list[Finding] = []
    seen: dict[str, tuple[Path, int, str]] = {}

    for path, text in managed_content_entries(repo):
        for start_line, paragraph in paragraphs(text):
            normalized = normalize_block(paragraph)
            if len(normalized) < 60:
                continue
            previous = seen.get(normalized)
            if previous and previous[0] != path:
                findings.append(
                    Finding(
                        "DUPLICATE_CONTENT_WARNING",
                        "warning",
                        relpath(path, repo),
                        start_line,
                        "Exact normalized context block duplicate found.",
                        {
                            "other_file": relpath(previous[0], repo),
                            "other_line": previous[1],
                            "preview": paragraph[:160],
                        },
                    )
                )
            else:
                seen[normalized] = (path, start_line, paragraph)

    sections: dict[str, list[tuple[Path, int, str]]] = {}
    for path, text in managed_content_entries(repo):
        for heading, line, body in sections_by_heading(text):
            normalized_heading = normalize_block(heading)
            if len(body.strip()) >= 80:
                sections.setdefault(normalized_heading, []).append((path, line, body))

    for entries in sections.values():
        for i, left in enumerate(entries):
            for right in entries[i + 1 :]:
                if left[0] == right[0]:
                    continue
                ratio = difflib.SequenceMatcher(
                    None,
                    normalize_block(left[2]),
                    normalize_block(right[2]),
                ).ratio()
                if ratio >= 0.88:
                    findings.append(
                        Finding(
                            "DUPLICATE_CONTENT_WARNING",
                            "warning",
                            relpath(right[0], repo),
                            right[1],
                            "Same heading has highly similar content in another shard.",
                            {
                                "other_file": relpath(left[0], repo),
                                "other_line": left[1],
                                "similarity": round(ratio, 3),
                                "preview": right[2].strip()[:160],
                            },
                        )
                    )
    return findings


def paragraphs(text: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    current: list[str] = []
    start_line = 1
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            if current:
                blocks.append((start_line, "\n".join(current).strip()))
                current = []
            continue
        if not current:
            start_line = lineno
        current.append(line)
    if current:
        blocks.append((start_line, "\n".join(current).strip()))
    return blocks


def normalize_block(text: str) -> str:
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[`*_#>\[\]().,:;{}]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def sections_by_heading(text: str) -> list[tuple[str, int, str]]:
    sections: list[tuple[str, int, str]] = []
    current_heading: str | None = None
    current_line = 1
    body: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = HEADING_RE.match(line)
        if match:
            if current_heading is not None:
                sections.append((current_heading, current_line, "\n".join(body)))
            current_heading = match.group(2)
            current_line = lineno
            body = []
        elif current_heading is not None:
            body.append(line)
    if current_heading is not None:
        sections.append((current_heading, current_line, "\n".join(body)))
    return sections


def section_text(text: str, heading: str) -> str:
    for current_heading, _line, body in sections_by_heading(text):
        if current_heading.strip().lower() == heading.lower():
            return body
    return ""


def section_start_line(text: str, heading: str) -> int:
    for current_heading, line, _body in sections_by_heading(text):
        if current_heading.strip().lower() == heading.lower():
            return line + 1
    return 1


def path_reference_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    root = contexts_dir(repo)
    findings: list[Finding] = []
    if not root.exists():
        return findings

    for path, text in managed_content_entries(repo):
        for match in CODE_SPAN_RE.finditer(text):
            value = match.group(1).strip()
            if not looks_like_repo_path(value, repo):
                continue
            target = resolve_repo_path(repo, root, value)
            if escapes_repo(repo, target):
                findings.append(
                    Finding(
                        "MISSING_SOURCE_PATH",
                        "warning",
                        relpath(path, repo),
                        line_for_offset(text, match.start()),
                        f"Backticked path escapes repository root: {value}.",
                        {"path": value},
                    )
                )
                continue
            if not path_exists_or_glob_base(target):
                findings.append(
                    Finding(
                        "MISSING_SOURCE_PATH",
                        "warning",
                        relpath(path, repo),
                        line_for_offset(text, match.start()),
                        f"Backticked repository path does not exist: {value}.",
                        {"path": value, "resolved_to": relpath(target, repo)},
                    )
                )
    return findings


def local_link_findings(repo: Path) -> list[Finding]:
    """Resolve Markdown links as Markdown does: relative to the containing file."""
    repo = repo.resolve()
    root = contexts_dir(repo)
    findings: list[Finding] = []
    if not root.exists():
        return findings

    for path, text in managed_content_entries(repo):
        for match in MARKDOWN_LINK_RE.finditer(text):
            raw = match.group(1).strip().strip("<>")
            # Ignore optional Markdown titles after an unquoted URL/path.
            target_value = re.split(r'\s+["\']', raw, maxsplit=1)[0]
            parsed = urlparse(target_value)
            if parsed.scheme or target_value.startswith(("#", "//")):
                continue
            link_path = unquote(parsed.path)
            if not link_path:
                continue
            target = Path(link_path)
            if not target.is_absolute():
                target = path.parent / target
            if target.exists():
                continue
            findings.append(
                Finding(
                    "LOCAL_LINK_TARGET_MISSING",
                    "warning",
                    relpath(path, repo),
                    line_for_offset(text, match.start()),
                    f"Local Markdown link target does not exist relative to this file: {target_value}.",
                    {
                        "target": target_value,
                        "resolved_to": relpath(target, repo),
                    },
                )
            )
    return findings


def generic_agent_rule_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    root = contexts_dir(repo)
    findings: list[Finding] = []
    if not root.exists():
        return findings
    patterns = (
        re.compile(r"\bsandbox(?:ed|ing)?\b", re.IGNORECASE),
        re.compile(
            r"\b(?:network|internet)\s+(?:access\s+)?(?:is\s+)?"
            r"(?:disabled|restricted|unavailable|blocked)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:do not|don't|never)\b[^\n]{0,80}\buntracked\b",
            re.IGNORECASE,
        ),
        re.compile(r"\buntracked\s+(?:file|files|change|changes)\b", re.IGNORECASE),
    )
    for path, text in managed_content_entries(repo):
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns):
                findings.append(
                    Finding(
                        "GENERIC_AGENT_RULE",
                        "warning",
                        relpath(path, repo),
                        lineno,
                        "Generic agent runtime guidance does not belong in repository context.",
                        {"line": line.strip()},
                    )
                )
    return findings


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def source_drift_findings(repo: Path) -> list[Finding]:
    """Report source activity newer than context as a candidate, not proof of drift."""
    repo = repo.resolve()
    root = contexts_dir(repo)
    context_files = list(iter_markdown_files(root))
    agents = agents_file(repo)
    if agents.exists():
        context_files.append(agents)
    if not context_files:
        return []
    try:
        probe = run_git(repo, "rev-parse", "--show-toplevel")
    except FileNotFoundError:
        return [
            Finding(
                "GIT_UNAVAILABLE",
                "info",
                None,
                None,
                "Git is unavailable; source-change drift candidates were not checked.",
            )
        ]
    if probe.returncode != 0:
        return [
            Finding(
                "GIT_UNAVAILABLE",
                "info",
                None,
                None,
                "Repository Git metadata is unavailable; source-change drift candidates were not checked.",
            )
        ]

    context_mtime = max(path.stat().st_mtime for path in context_files)
    log = run_git(
        repo,
        "log",
        f"--since=@{int(context_mtime)}",
        "--format=%H%x09%cI",
        "--",
        ".",
        ":(exclude).agents/contexts/**",
        ":(exclude)AGENTS.md",
    )
    commits = (
        [line for line in log.stdout.splitlines() if line.strip()]
        if log.returncode == 0
        else []
    )

    dirty_names: set[str] = set()
    for args in (
        ("diff", "--name-only", "-z"),
        ("diff", "--cached", "--name-only", "-z"),
    ):
        result = run_git(repo, *args)
        if result.returncode == 0:
            dirty_names.update(name for name in result.stdout.split("\0") if name)
    dirty_newer: list[str] = []
    for name in sorted(dirty_names):
        if name == "AGENTS.md" or name.startswith(".agents/contexts/"):
            continue
        source = repo / name
        if source.exists() and source.stat().st_mtime > context_mtime:
            dirty_newer.append(name)

    if not commits and not dirty_newer:
        return []
    return [
        Finding(
            "SOURCE_CHANGED_SINCE_CONTEXT",
            "warning",
            relpath(root, repo),
            None,
            "Git shows source activity newer than context; review it as a drift candidate only.",
            {
                "context_mtime": context_mtime,
                "newer_commits": commits,
                "newer_dirty_tracked_files": dirty_newer,
                "semantic_verification": "not_performed",
            },
        )
    ]


def looks_like_repo_path(value: str, repo: Path) -> bool:
    if not value or is_external_reference(value):
        return False
    if any(char.isspace() for char in value):
        return False
    if value.startswith("/"):
        return False
    command_prefixes = {
        "python",
        "python3",
        "uv",
        "npm",
        "pnpm",
        "yarn",
        "docker",
        "alembic",
        "git",
    }
    first = value.split("/", 1)[0]
    if first in command_prefixes:
        return False
    if value.startswith(("./", "../")):
        return True

    if (repo / first).exists():
        return True

    return False


def resolve_repo_path(repo: Path, root: Path, value: str) -> Path:
    value = strip_anchor(value)
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if value.endswith(".md") and "/" not in value and (root / value).exists():
        return root / value
    return repo / candidate


def escapes_repo(repo: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(repo.resolve())
        return False
    except ValueError:
        return True


def path_exists_or_glob_base(path: Path) -> bool:
    raw = str(path)
    if "*" not in raw and "?" not in raw:
        return path.exists()
    parts = path.parts
    base_parts: list[str] = []
    for part in parts:
        if "*" in part or "?" in part:
            break
        base_parts.append(part)
    if not base_parts:
        return False
    return Path(*base_parts).exists()


def audit_findings(repo: Path) -> list[Finding]:
    findings: list[Finding] = []

    struct_findings = structural_findings(repo)
    findings.extend(struct_findings)
    if any(f.severity == "error" for f in struct_findings):
        return findings

    findings.extend(lint_findings(repo))
    findings.extend(lazy_loading_findings(repo))
    findings.extend(eager_shard_bundle_findings(repo))
    findings.extend(size_findings(repo))
    findings.extend(duplicate_findings(repo))
    findings.extend(identifier_density_findings(repo))
    findings.extend(path_reference_findings(repo))
    findings.extend(local_link_findings(repo))
    findings.extend(generic_agent_rule_findings(repo))
    findings.extend(source_drift_findings(repo))
    return findings


def status_findings(repo: Path) -> list[Finding]:
    repo = repo.resolve()
    root = contexts_dir(repo)
    findings = structural_findings(repo)
    if not root.exists():
        return findings

    total_tokens = 0
    entries = managed_content_entries(repo)
    for path, text in entries:
        tokens = estimated_tokens(text)
        total_tokens += tokens
        findings.append(
            Finding(
                "CONTEXT_STATUS_SUMMARY",
                "info",
                relpath(path, repo),
                None,
                "Context file size summary.",
                {
                    "estimated_tokens": tokens,
                    "non_empty_lines": len([line for line in text.splitlines() if line.strip()]),
                },
            )
        )
    findings.append(
        Finding(
            "CONTEXT_STATUS_SUMMARY",
            "info",
            relpath(root, repo),
            None,
            "Context status summary.",
            {"files": len(entries), "estimated_tokens": total_tokens},
        )
    )
    return findings


def build_report(command: str, repo: Path, findings: list[Finding]) -> dict:
    summary = {
        "errors": sum(1 for finding in findings if finding.severity == "error"),
        "warnings": sum(1 for finding in findings if finding.severity == "warning"),
        "info": sum(1 for finding in findings if finding.severity == "info"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "repo": str(repo),
        "summary": summary,
        "findings": [finding.to_dict() for finding in findings],
        "semantic_source_verification": SEMANTIC_NOT_PERFORMED,
    }


def exit_code(findings: list[Finding]) -> int:
    if any(finding.severity == "error" for finding in findings):
        return 2
    if any(finding.severity == "warning" for finding in findings):
        return 1
    return 0


def print_report(report: dict, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=False))
        return

    findings = report["findings"]
    if findings:
        for finding in findings:
            location = finding["file"] or "<repo>"
            if finding["line"] is not None:
                location = f"{location}:{finding['line']}"
            print(
                f"{finding['severity']}: {finding['code']}: "
                f"{location}: {finding['message']}"
            )
            if finding["details"]:
                detail = json.dumps(finding["details"], sort_keys=True)
                print(f"  details: {detail}")
    else:
        print("no static findings")

    summary = report["summary"]
    print(
        f"summary: {summary['errors']} error(s), "
        f"{summary['warnings']} warning(s), {summary['info']} info"
    )
    if summary["errors"]:
        print("Static context quality checks failed.")
    elif summary["warnings"]:
        print("Static context quality checks completed with warnings.")
    else:
        print("Static context quality checks passed.")
    print("Semantic accuracy against repository sources was not verified.")


def run_report(
    command: str,
    repo: Path,
    output_format: str,
    findings: list[Finding],
    *,
    advisory: bool = False,
    strict: bool = False,
) -> int:
    report = build_report(command, repo, findings)
    print_report(report, output_format)
    if advisory and not strict:
        return 2 if any(finding.severity == "error" for finding in findings) else 0
    return exit_code(findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Context management helper operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create minimal .agents/contexts files.")
    init_parser.add_argument("repo", nargs="?", default=".", help="Repository path.")
    init_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing context files.")

    for name, help_text in (
        ("lint", "Check deterministic content hygiene."),
        ("scan", "Alias for lint."),
        ("validate", "Validate context structure."),
        ("audit", "Run static context quality checks."),
        ("status", "Summarize context status."),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("repo", nargs="?", default=".", help="Repository path.")
        sub.add_argument("--format", choices=("text", "json"), default="text")
        if name == "audit":
            sub.add_argument(
                "--strict",
                action="store_true",
                help="Return exit 1 when advisory warnings are present.",
            )

    args = parser.parse_args(argv)
    repo = Path(args.repo)

    if args.command == "init":
        return init_context(repo, args.overwrite)
    if args.command == "lint":
        return run_report("lint", repo, args.format, lint_findings(repo))
    if args.command == "scan":
        return run_report("scan", repo, args.format, lint_findings(repo))
    if args.command == "validate":
        return run_report("validate", repo, args.format, structural_findings(repo))
    if args.command == "audit":
        return run_report(
            "audit",
            repo,
            args.format,
            audit_findings(repo),
            advisory=True,
            strict=args.strict,
        )
    if args.command == "status":
        return run_report("status", repo, args.format, status_findings(repo))

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
