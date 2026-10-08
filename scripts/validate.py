#!/usr/bin/env python3
"""Consistency checks for the cortese-prospects pipeline data.

Reads prospects.csv, the LIVE send queue (outreach/queue-YYYY-MM-DD.txt, one file
per send date), the legacy queue outreach/manifest.csv, the optional
outreach/do_not_contact.csv, and the outreach/*.md drafts. Standard library only;
no network access.

Exit code: 1 if any ERROR (hard failure), 0 otherwise. Warnings never change the
exit code unless --strict is given. Send-safety and structural problems are
errors; data-quality problems are warnings.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

PROSPECT_COLUMNS = [
    "business_name", "category", "town", "region", "phone", "website",
    "online_ordering", "call_volume_indicator", "chain_or_independent",
    "source_url", "priority", "pitch_angle",
]
MANIFEST_COLUMNS = ["slug", "business", "email_draft_file", "status(queued)"]
MANIFEST_STATUS = "status(queued)"
QUEUED = "queued"
REQUIRED_PROSPECT_FIELDS = ["business_name", "town", "phone", "source_url", "priority"]
PRIORITIES = {"A", "B", "C", "drop"}
OPT_OUT_FRAGMENT = "reply STOP to opt out"  # case-sensitive on purpose
PHONE_RE = re.compile(r"^\(\d{3}\) \d{3}-\d{4}$")
EMAIL_RE = re.compile(r"^[^@\s|]+@[^@\s|]+\.[A-Za-z]{2,}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUEUE_FILE_RE = re.compile(r"^queue-(\d{4}-\d{2}-\d{2})\.txt$")
TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")
VOCAB = {
    "online_ordering": {"yes", "no", "unknown"},
    "call_volume_indicator": {"low", "medium", "medium-high", "high", "very high"},
    "chain_or_independent": {"independent", "chain"},
}
HINT_PREFIX = 7  # normalized chars compared when looking for a near-match
README_COUNT_RE = re.compile(r"\*\*`prospects\.csv`\*\*\s*[—-]\s*(\d+)\s+verified leads")
DNC_LABEL = "outreach/do_not_contact.csv"

# Output sections, printed in this order.
S_LIVE = "live queue (outreach/queue-*.txt)"
S_LEGACY = "legacy manifest (outreach/manifest.csv; not the live send queue)"
S_DATA = "prospects, drafts and docs"
SECTION_ORDER = (S_LIVE, S_LEGACY, S_DATA)

# Warning groups, printed in this order within a section.
W_ORPHAN = "queued business has no exact prospects.csv match (orphan queue entry)"
W_DNC_LEGACY = "entry is on outreach/do_not_contact.csv (blocked; legacy queue is not sent from)"
W_MALFORMED = "malformed queue line"
W_EMAIL = "malformed email"
W_DUPLICATE = "duplicate within the same date's queue file"
W_UNDATED = "queue file name is not queue-YYYY-MM-DD.txt (checked anyway)"
W_STATUS = "manifest status is not 'queued'"
W_PHONE = "phone not in (NNN) NNN-NNNN format"
W_VOCAB = "value outside controlled vocabulary"
W_README = "README lead count differs from prospects.csv"
WARNING_ORDER = (
    W_ORPHAN, W_DNC_LEGACY, W_MALFORMED, W_EMAIL, W_DUPLICATE, W_UNDATED,
    W_STATUS, W_PHONE, W_VOCAB, W_README,
)


class Report:
    def __init__(self) -> None:
        self.errors: dict[str, list[str]] = defaultdict(list)
        self.warnings: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    def error(self, msg: str, section: str = S_DATA) -> None:
        self.errors[section].append(msg)

    def warn(self, group: str, msg: str, section: str = S_DATA) -> None:
        self.warnings[section][group].append(msg)

    @property
    def error_count(self) -> int:
        return sum(len(v) for v in self.errors.values())

    @property
    def warning_count(self) -> int:
        return sum(len(items) for groups in self.warnings.values() for items in groups.values())


def _fold(value: str) -> str:
    """NFKD-decompose, drop combining marks (accents), casefold."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def name_key(value: str) -> str:
    """Exact-lookup key: accents removed, trimmed, whitespace collapsed, casefolded."""
    return " ".join(_fold(value).split())


def _hint_key(name: str) -> str:
    """Looser key for near-matches: alphanumerics only, any parenthetical removed."""
    return re.sub(r"[^0-9a-z]", "", re.sub(r"\(.*?\)", "", _fold(name)))


def near_matches(business: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    key = _hint_key(business)[:HINT_PREFIX]
    if not key:
        return []
    return [r for r in rows if _hint_key(r["business_name"])[:HINT_PREFIX] == key]


def read_text(path: Path, label: str, report: Report, section: str = S_DATA) -> str | None:
    """Decode a file as UTF-8 (a leading BOM is dropped); hard error if invalid."""
    try:
        return path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        report.error(f"{label}: not valid UTF-8 (byte {exc.start})", section)
        return None


def read_csv(
    path: Path, label: str, expected: list[str], report: Report, section: str = S_DATA
) -> list[dict[str, str]] | None:
    """Return rows as dicts, or None if the file is structurally unusable."""
    if not path.is_file():
        report.error(f"{label}: file not found", section)
        return None
    text = read_text(path, label, report, section)
    if text is None:
        return None
    raw = list(csv.reader(io.StringIO(text, newline="")))
    if not raw:
        report.error(f"{label}: file is empty", section)
        return None
    header = raw[0]
    if header != expected:
        report.error(f"{label}: header {header} does not match expected {expected}", section)
        return None
    rows: list[dict[str, str]] = []
    for lineno, fields in enumerate(raw[1:], start=2):
        if not fields:
            continue  # blank line
        if len(fields) != len(expected):
            report.error(f"{label} line {lineno}: {len(fields)} fields, expected {len(expected)}", section)
            continue
        row = dict(zip(expected, fields))
        row["_line"] = str(lineno)
        rows.append(row)
    return rows


class DoNotContact:
    """Optional outreach/do_not_contact.csv: needs `business`; `email` is optional."""

    def __init__(self) -> None:
        self.businesses: set[str] = set()
        self.emails: set[str] = set()

    @classmethod
    def load(cls, path: Path, report: Report) -> "DoNotContact":
        dnc = cls()
        if not path.is_file():
            return dnc
        text = read_text(path, DNC_LABEL, report)
        if text is None:
            return dnc
        reader = csv.DictReader(io.StringIO(text, newline=""))
        fields = reader.fieldnames or []
        if "business" not in fields:
            report.error(f"{DNC_LABEL}: missing required 'business' column")
            return dnc
        for row in reader:
            dnc.businesses.add(name_key(row.get("business") or ""))
            if "email" in fields:
                dnc.emails.add(name_key(row.get("email") or ""))
        dnc.businesses.discard("")
        dnc.emails.discard("")
        return dnc

    def reason(self, business_names: list[str], email: str = "") -> str | None:
        if any(name_key(b) in self.businesses for b in business_names):
            return "business is on " + DNC_LABEL
        if email and name_key(email) in self.emails:
            return "email is on " + DNC_LABEL
        return None


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
            report.error(f"{where}: priority {r['priority']!r} not in {sorted(PRIORITIES)}")
        if r["phone"].strip() and not PHONE_RE.match(r["phone"]):
            report.warn(W_PHONE, f"{where}: {r['phone']!r}")
        for field, allowed in VOCAB.items():
            if r[field] not in allowed:
                report.warn(W_VOCAB, f"{where}: {field}={r[field]!r}")


def check_against_prospects(
    names: list[str],
    label: str,
    where: str,
    prospects: list[dict[str, str]],
    by_key: dict[str, list[dict[str, str]]],
    report: Report,
    section: str,
) -> None:
    """Drop / near-drop (hard) and orphan (warning) checks for one queued business.

    `names` are lookup candidates, most specific first (e.g. the raw queue text,
    then the same text with a trailing "(Location)" removed).
    """
    for name in names:
        matches = by_key.get(name_key(name), [])
        if matches:
            if all(p["priority"] == "drop" for p in matches):
                report.error(f"{where}: queued business is marked priority=drop in prospects.csv", section)
            return
    hints = near_matches(names[-1], prospects)
    if hints and all(p["priority"] == "drop" for p in hints):
        rows = "; ".join(f"{p['business_name']} (line {p['_line']})" for p in hints)
        report.error(f"{where}: queued business near-matches a dropped prospect: {rows}", section)
        return
    if hints:
        suffix = " — possible near-match, verify: " + "; ".join(
            p["business_name"] + (" [drop]" if p["priority"] == "drop" else "") for p in hints
        )
    else:
        suffix = " — no similar name"
    report.warn(W_ORPHAN, f"{label}{suffix}", section)


def index_prospects(prospects: list[dict[str, str]] | None) -> dict[str, list[dict[str, str]]]:
    by_key: dict[str, list[dict[str, str]]] = defaultdict(list)
    for p in prospects or []:
        by_key[name_key(p["business_name"])].append(p)
    return by_key


def check_manifest(
    manifest: list[dict[str, str]],
    prospects: list[dict[str, str]] | None,
    dnc: DoNotContact,
    outreach_dir: Path,
    report: Report,
) -> None:
    by_key = index_prospects(prospects)
    for field in ("slug", "business"):
        seen: dict[str, list[str]] = defaultdict(list)
        for m in manifest:
            seen[name_key(m[field])].append(m[field])
        for variants in seen.values():
            if len(variants) > 1:
                shown = ", ".join(repr(v) for v in variants)
                report.error(f"outreach/manifest.csv: duplicate {field} {shown} ({len(variants)} rows)", S_LEGACY)

    for m in manifest:
        where = f"outreach/manifest.csv line {m['_line']} ({m['business']})"
        draft = m["email_draft_file"].strip()
        if not draft or Path(draft).name != draft:
            report.error(f"{where}: email_draft_file {draft!r} must be a bare filename", S_LEGACY)
        elif not (outreach_dir / draft).is_file():
            report.error(f"{where}: draft outreach/{draft} does not exist", S_LEGACY)
        if m[MANIFEST_STATUS] != QUEUED:
            report.warn(W_STATUS, f"{where}: status {m[MANIFEST_STATUS]!r}", S_LEGACY)
        blocked = dnc.reason([m["business"]])
        if blocked:
            report.warn(W_DNC_LEGACY, f"{where}: {blocked}", S_LEGACY)
        if prospects is not None:
            check_against_prospects(
                [m["business"]], f"{m['business']} (slug {m['slug']})", where,
                prospects, by_key, report, S_LEGACY,
            )


def queue_files(outreach_dir: Path, today: dt.date, all_queues: bool, report: Report) -> list[Path]:
    """Live queue files to check: dated today or later, or all with --all-queues."""
    selected = []
    for path in sorted(outreach_dir.glob("queue-*.txt")) if outreach_dir.is_dir() else []:
        m = QUEUE_FILE_RE.match(path.name)
        date = None
        if m:
            try:
                date = dt.date.fromisoformat(m.group(1))
            except ValueError:
                date = None
        if date is None:
            report.warn(W_UNDATED, f"outreach/{path.name}", S_LIVE)
            selected.append(path)
        elif all_queues or date >= today:
            selected.append(path)
    return selected


def parse_queue_line(line: str) -> tuple[str, str] | None:
    """Return (first_field, business) or None if the line is malformed."""
    fields = [f.strip() for f in line.split("|")]
    if len(fields) < 2 or not fields[0] or not fields[1]:
        return None
    return fields[0], fields[1]


def check_live_queue(
    path: Path,
    prospects: list[dict[str, str]] | None,
    dnc: DoNotContact,
    report: Report,
) -> int:
    """Check one dated queue file; return the number of entries parsed."""
    label = f"outreach/{path.name}"
    text = read_text(path, label, report, S_LIVE)
    if text is None:
        return 0
    by_key = index_prospects(prospects)
    seen_email: dict[str, list[str]] = defaultdict(list)
    seen_business: dict[str, list[str]] = defaultdict(list)
    entries = 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        where = f"{label}:{lineno}"
        parsed = parse_queue_line(line)
        if parsed is None:
            report.warn(W_MALFORMED, f"{where}: {line[:80]!r}", S_LIVE)
            continue
        entries += 1
        first, business = parsed
        bare = TRAILING_PAREN_RE.sub("", business) or business
        names = [business] if bare == business else [business, bare]
        where = f"{where} ({business})"
        is_email = "@" in first
        if is_email and not EMAIL_RE.match(first):
            report.warn(W_EMAIL, f"{where}: {first!r}", S_LIVE)
        elif not is_email and not SLUG_RE.match(first):
            report.warn(W_EMAIL, f"{where}: {first!r} is neither an email nor a slug", S_LIVE)
        if is_email:
            seen_email[name_key(first)].append(where)
        seen_business[name_key(bare)].append(where)
        blocked = dnc.reason(names, first if is_email else "")
        if blocked:
            report.error(f"{where}: {blocked}", S_LIVE)
        if prospects is not None:
            check_against_prospects(names, f"{business} [{where.split(' ')[0]}]", where,
                                    prospects, by_key, report, S_LIVE)
    for kind, seen in (("email", seen_email), ("business", seen_business)):
        for key, places in seen.items():
            if len(places) > 1:
                report.warn(W_DUPLICATE, f"{kind} {key!r} appears {len(places)}x: " + "; ".join(places), S_LIVE)
    return entries


def check_drafts(outreach_dir: Path, report: Report) -> list[Path]:
    """Every draft must carry the opt-out line. README*.md files are docs, not drafts."""
    drafts = [
        d for d in sorted(outreach_dir.glob("*.md")) if not d.name.upper().startswith("README")
    ] if outreach_dir.is_dir() else []
    for d in drafts:
        label = f"outreach/{d.name}"
        text = read_text(d, label, report)
        if text is not None and OPT_OUT_FRAGMENT not in text:
            report.error(f"{label}: missing opt-out line '{OPT_OUT_FRAGMENT}'")
    return drafts


def check_readme(readme: Path, prospects: list[dict[str, str]], report: Report) -> None:
    if not readme.is_file():
        return
    text = read_text(readme, "README.md", report)
    if text is None:
        return
    m = README_COUNT_RE.search(text)
    if not m:
        return
    stated = int(m.group(1))
    actual = sum(1 for p in prospects if p["priority"] != "drop")
    if stated != actual:
        report.warn(W_README, f"README says {stated} verified leads; prospects.csv has {actual} non-drop rows")


def validate(repo: Path, today: dt.date | None = None, all_queues: bool = False) -> tuple[Report, dict]:
    report = Report()
    today = today or dt.date.today()
    outreach_dir = repo / "outreach"
    prospects = read_csv(repo / "prospects.csv", "prospects.csv", PROSPECT_COLUMNS, report)
    if prospects is not None:
        check_prospects(prospects, report)
    dnc = DoNotContact.load(outreach_dir / "do_not_contact.csv", report)

    live = queue_files(outreach_dir, today, all_queues, report)
    live_entries = sum(check_live_queue(p, prospects, dnc, report) for p in live)

    manifest = read_csv(outreach_dir / "manifest.csv", "outreach/manifest.csv", MANIFEST_COLUMNS, report, S_LEGACY)
    if manifest is not None:
        check_manifest(manifest, prospects, dnc, outreach_dir, report)
    drafts = check_drafts(outreach_dir, report)
    if prospects is not None:
        check_readme(repo / "README.md", prospects, report)
    counts = {
        "prospects": len(prospects or []),
        "drafts": len(drafts),
        "queued": len(manifest or []),
        "live_entries": live_entries,
        "live_files": [p.name for p in live],
        "today": today.isoformat(),
        "all_queues": all_queues,
    }
    return report, counts


def print_report(report: Report, counts: dict, strict: bool) -> None:
    scope = "all dates" if counts["all_queues"] else f"dated {counts['today']} or later"
    files = ", ".join(counts["live_files"]) or "none"
    print(f"live queue files checked ({scope}): {files}")
    print()
    if report.errors:
        print(f"ERRORS ({report.error_count}):")
        for section in SECTION_ORDER:
            items = report.errors.get(section)
            if not items:
                continue
            print(f"  {section}:")
            for e in items:
                print(f"    - {e}")
        print()
    if report.warning_count:
        label = "WARNINGS (treated as errors: --strict)" if strict else "WARNINGS"
        print(f"{label} ({report.warning_count}):")
        for section in SECTION_ORDER:
            groups = report.warnings.get(section)
            if not groups:
                continue
            print(f"  {section}:")
            for group in WARNING_ORDER:
                items = groups.get(group)
                if not items:
                    continue
                print(f"    [{len(items)}] {group}:")
                for item in items:
                    print(f"      - {item}")
        print()
    nfiles = len(counts["live_files"])
    print(
        f"checked {counts['prospects']} prospects, {counts['drafts']} drafts, "
        f"{counts['live_entries']} live queue entries in {nfiles} file{'s' if nfiles != 1 else ''}, "
        f"{counts['queued']} legacy manifest rows: {report.error_count} errors, "
        f"{report.warning_count} warnings"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parent.parent,
        help="repo root to check (default: this script's repo)",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument(
        "--all-queues", action="store_true",
        help="also check queue-YYYY-MM-DD.txt files dated before today",
    )
    parser.add_argument(
        "--today", type=dt.date.fromisoformat, default=None, metavar="YYYY-MM-DD",
        help="override today's date (box local) for queue selection; used by tests",
    )
    args = parser.parse_args(argv)
    report, counts = validate(args.repo, args.today, args.all_queues)
    print_report(report, counts, args.strict)
    failed = bool(report.error_count) or (args.strict and report.warning_count > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
