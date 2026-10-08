#!/usr/bin/env python3
"""Consistency checks for the cortese-prospects pipeline data.

Reads prospects.csv, outreach/manifest.csv (the authoritative send queue) and
outreach/*.md. Standard library only; no network access.

Exit code: 1 if any ERROR (hard failure), 0 otherwise. Warnings never change the
exit code unless --strict is given. Data-quality problems are warnings until the
ticket-1 S2 queue cleanup lands; structural/safety problems are errors.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROSPECT_COLUMNS = [
    "business_name", "category", "town", "region", "phone", "website",
    "online_ordering", "call_volume_indicator", "chain_or_independent",
    "source_url", "priority", "pitch_angle",
]
MANIFEST_COLUMNS = ["slug", "business", "email_draft_file", "status(queued)"]
REQUIRED_PROSPECT_FIELDS = ["business_name", "town", "phone", "source_url", "priority"]
PRIORITIES = {"A", "B", "C", "drop"}
OPT_OUT_FRAGMENT = "reply STOP to opt out"
PHONE_RE = re.compile(r"^\(\d{3}\) \d{3}-\d{4}$")
VOCAB = {
    "online_ordering": {"yes", "no", "unknown"},
    "call_volume_indicator": {"low", "medium", "medium-high", "high", "very high"},
    "chain_or_independent": {"independent", "chain"},
}
HINT_PREFIX = 7  # normalized chars compared when suggesting a near-match for an orphan
README_COUNT_RE = re.compile(r"\*\*`prospects\.csv`\*\*\s*[—-]\s*(\d+)\s+verified leads")

# Warning groups, printed in this order.
W_ORPHAN = "queued business has no exact prospects.csv match (orphan queue entry)"
W_PHONE = "phone not in (NNN) NNN-NNNN format"
W_VOCAB = "value outside controlled vocabulary"
W_README = "README lead count differs from prospects.csv"


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: dict[str, list[str]] = defaultdict(list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, group: str, msg: str) -> None:
        self.warnings[group].append(msg)

    @property
    def warning_count(self) -> int:
        return sum(len(v) for v in self.warnings.values())


def read_csv(path: Path, expected: list[str], report: Report) -> list[dict[str, str]] | None:
    """Return rows as dicts, or None if the file is structurally unusable."""
    name = path.name if path.parent.name != "outreach" else f"outreach/{path.name}"
    if not path.is_file():
        report.error(f"{name}: file not found")
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        raw = list(csv.reader(fh))
    if not raw:
        report.error(f"{name}: file is empty")
        return None
    header = raw[0]
    if header != expected:
        report.error(f"{name}: header {header} does not match expected {expected}")
        return None
    rows: list[dict[str, str]] = []
    for lineno, fields in enumerate(raw[1:], start=2):
        if not fields:
            continue  # blank line
        if len(fields) != len(expected):
            report.error(
                f"{name} line {lineno}: {len(fields)} fields, expected {len(expected)}"
            )
            continue
        row = dict(zip(expected, fields))
        row["_line"] = str(lineno)
        rows.append(row)
    return rows


def _norm(name: str) -> str:
    """Lowercase alphanumerics with any parenthetical removed (for near-match hints only)."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\(.*?\)", "", name.lower()))


def near_matches(business: str, names: list[str]) -> list[str]:
    key = _norm(business)[:HINT_PREFIX]
    return [n for n in names if key and _norm(n)[:HINT_PREFIX] == key]


def check_prospects(rows: list[dict[str, str]], report: Report) -> None:
    for r in rows:
        where = f"prospects.csv line {r['_line']} ({r['business_name'] or '?'})"
        for field in REQUIRED_PROSPECT_FIELDS:
            if not r[field].strip():
                report.error(f"{where}: empty {field}")
        src = r["source_url"].strip()
        if src and not src.startswith(("http://", "https://")):
            report.error(f"{where}: source_url is not an http(s) URL: {src!r}")
        if r["priority"].strip() and r["priority"] not in PRIORITIES:
            report.error(
                f"{where}: priority {r['priority']!r} not in {sorted(PRIORITIES)}"
            )
        if r["phone"].strip() and not PHONE_RE.match(r["phone"]):
            report.warn(W_PHONE, f"{where}: {r['phone']!r}")
        for field, allowed in VOCAB.items():
            if r[field] not in allowed:
                report.warn(W_VOCAB, f"{where}: {field}={r[field]!r}")


def check_manifest(
    manifest: list[dict[str, str]],
    prospects: list[dict[str, str]] | None,
    outreach_dir: Path,
    report: Report,
) -> None:
    by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for p in prospects or []:
        by_name[p["business_name"]].append(p)

    for field in ("slug", "business"):
        for value, n in Counter(m[field] for m in manifest).items():
            if n > 1:
                report.error(f"outreach/manifest.csv: duplicate {field} {value!r} ({n} rows)")

    for m in manifest:
        where = f"outreach/manifest.csv line {m['_line']} ({m['business']})"
        draft = m["email_draft_file"].strip()
        if not draft or Path(draft).name != draft:
            report.error(f"{where}: email_draft_file {draft!r} must be a bare filename")
        elif not (outreach_dir / draft).is_file():
            report.error(f"{where}: draft outreach/{draft} does not exist")
        if prospects is None:
            continue
        matches = by_name.get(m["business"], [])
        if not matches:
            hint = near_matches(m["business"], list(by_name))
            suffix = f" — possible near-match, verify: {'; '.join(hint)}" if hint else " — no similar name"
            report.warn(W_ORPHAN, f"{m['business']} (slug {m['slug']}){suffix}")
        elif all(p["priority"] == "drop" for p in matches):
            report.error(f"{where}: queued business is marked priority=drop in prospects.csv")


def check_do_not_contact(manifest: list[dict[str, str]], path: Path, report: Report) -> None:
    """Optional list (planned for S2). Only read if present; needs a `business` column."""
    if not path.is_file():
        return
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if "business" not in (reader.fieldnames or []):
            report.error("outreach/do_not_contact.csv: missing required 'business' column")
            return
        blocked = {row["business"].strip() for row in reader if row["business"].strip()}
    for m in manifest:
        if m["business"] in blocked:
            report.error(
                f"outreach/manifest.csv line {m['_line']} ({m['business']}): "
                "business is on outreach/do_not_contact.csv"
            )


def check_drafts(outreach_dir: Path, report: Report) -> list[Path]:
    drafts = sorted(outreach_dir.glob("*.md")) if outreach_dir.is_dir() else []
    for d in drafts:
        if OPT_OUT_FRAGMENT not in d.read_text(encoding="utf-8"):
            report.error(f"outreach/{d.name}: missing opt-out line '{OPT_OUT_FRAGMENT}'")
    return drafts


def check_readme(readme: Path, prospects: list[dict[str, str]], report: Report) -> None:
    if not readme.is_file():
        return
    m = README_COUNT_RE.search(readme.read_text(encoding="utf-8"))
    if not m:
        return
    stated = int(m.group(1))
    actual = sum(1 for p in prospects if p["priority"] != "drop")
    if stated != actual:
        report.warn(W_README, f"README says {stated} verified leads; prospects.csv has {actual} non-drop rows")


def validate(repo: Path) -> tuple[Report, dict[str, int]]:
    report = Report()
    outreach_dir = repo / "outreach"
    prospects = read_csv(repo / "prospects.csv", PROSPECT_COLUMNS, report)
    if prospects is not None:
        check_prospects(prospects, report)
    manifest = read_csv(outreach_dir / "manifest.csv", MANIFEST_COLUMNS, report)
    if manifest is not None:
        check_manifest(manifest, prospects, outreach_dir, report)
        check_do_not_contact(manifest, outreach_dir / "do_not_contact.csv", report)
    drafts = check_drafts(outreach_dir, report)
    if prospects is not None:
        check_readme(repo / "README.md", prospects, report)
    counts = {
        "prospects": len(prospects or []),
        "drafts": len(drafts),
        "queued": len(manifest or []),
    }
    return report, counts


def print_report(report: Report, counts: dict[str, int], strict: bool) -> None:
    if report.errors:
        print(f"ERRORS ({len(report.errors)}):")
        for e in report.errors:
            print(f"  - {e}")
        print()
    if report.warnings:
        label = "WARNINGS (treated as errors: --strict)" if strict else "WARNINGS"
        print(f"{label} ({report.warning_count}):")
        for group in (W_ORPHAN, W_PHONE, W_VOCAB, W_README):
            items = report.warnings.get(group)
            if not items:
                continue
            print(f"  [{len(items)}] {group}:")
            for item in items:
                print(f"    - {item}")
        print()
    print(
        f"checked {counts['prospects']} prospects, {counts['drafts']} drafts, "
        f"{counts['queued']} queued: {len(report.errors)} errors, "
        f"{report.warning_count} warnings"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parent.parent,
        help="repo root to check (default: this script's repo)",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)
    report, counts = validate(args.repo)
    print_report(report, counts, args.strict)
    failed = bool(report.errors) or (args.strict and report.warning_count > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
