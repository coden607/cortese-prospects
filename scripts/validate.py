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
EMAIL_TOKEN_RE = re.compile(r"[^\s|<>,;:()\[\]\"']+@[^\s|<>,;:()\[\]\"']+")
MAILTO_RE = re.compile(r"^mailto:", re.IGNORECASE)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUEUE_FILE_RE = re.compile(r"^queue-(.*)\.txt$", re.IGNORECASE)
QUEUE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
QUEUE_DOCS = {"readme-queue.md"}  # outreach files allowed to contain "queue" without being queues
DRAFT_EXEMPT = {"README-QUEUE.md", "README.md"}  # docs in outreach/, not email drafts
TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")
VOCAB = {
    "online_ordering": {"yes", "no", "unknown"},
    "call_volume_indicator": {"low", "medium", "medium-high", "high", "very high"},
    "chain_or_independent": {"independent", "chain"},
}
HINT_PREFIX = 7  # normalized chars compared when looking for a near-match
MIN_PREFIX = 5  # shorter key must be at least this long for a prefix near-match
APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'"})
LEADING_THE_RE = re.compile(r"^the\s+")
# Generic words dropped from the "core" key used only for conservative do-not-contact matching.
GENERIC_WORDS = {
    "restaurant", "ristorante", "pizzeria", "pizza", "bar", "grill", "grille", "tavern",
    "cafe", "diner", "pub", "bistro", "kitchen", "and", "inc", "llc", "co", "the",
}
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
W_REQUEUE = "email previously queued on an earlier date (past file, not selected)"
W_UNDATED = "queue file name is not queue-YYYY-MM-DD.txt (checked anyway)"
W_QUEUE_LIKE = "file name contains 'queue' but is not a queue-YYYY-MM-DD.txt file (not checked)"
W_STATUS = "manifest status is not 'queued'"
W_PHONE = "phone not in (NNN) NNN-NNNN format"
W_VOCAB = "value outside controlled vocabulary"
W_README = "README lead count differs from prospects.csv"
WARNING_ORDER = (
    W_ORPHAN, W_DNC_LEGACY, W_MALFORMED, W_EMAIL, W_REQUEUE, W_UNDATED, W_QUEUE_LIKE,
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
    """Curly/modifier apostrophes to ', NFKD-decompose, drop combining marks, casefold."""
    decomposed = unicodedata.normalize("NFKD", value.translate(APOSTROPHES))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def name_key(value: str) -> str:
    """Exact-lookup key: folded, trimmed, whitespace collapsed, leading 'the ' removed."""
    return LEADING_THE_RE.sub("", " ".join(_fold(value).split()))


def _hint_key(name: str) -> str:
    """Looser key for near-matches: alphanumerics only, parentheticals and leading 'the' removed."""
    no_paren = re.sub(r"\(.*?\)", "", _fold(name)).strip()
    return re.sub(r"[^0-9a-z]", "", LEADING_THE_RE.sub("", no_paren))


def _core_key(name: str) -> str:
    """Hint key with generic words (pizza, restaurant, bar, grill...) removed."""
    no_paren = re.sub(r"\(.*?\)", "", _fold(name)).replace("'", "")
    words = re.findall(r"[0-9a-z]+", no_paren)
    return "".join(w for w in words if w not in GENERIC_WORDS)


def prefix_match(a: str, b: str) -> bool:
    """True if either key is a prefix of the other and the shorter has >= MIN_PREFIX chars."""
    short, long_ = sorted((a, b), key=len)
    return len(short) >= MIN_PREFIX and long_.startswith(short)


def is_near(a: str, b: str) -> bool:
    ka, kb = _hint_key(a), _hint_key(b)
    if not ka or not kb:
        return False
    return ka[:HINT_PREFIX] == kb[:HINT_PREFIX] or prefix_match(ka, kb)


def near_matches(business: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Rows whose hint key shares the first HINT_PREFIX chars or is a prefix either way.

    Known gap: a word inserted in the middle ("Sorge's Italian Restaurant" vs "Sorge's
    Restaurant") defeats both rules; such entries still surface as orphan warnings.
    """
    return [r for r in rows if is_near(business, r["business_name"])]


def strip_mailto(value: str) -> str:
    return MAILTO_RE.sub("", value.strip()).strip()


def slug_names(slug: str) -> list[str]:
    """Name candidates from a slug: 'sharkeys-binghamton' -> 'sharkeys binghamton', 'sharkeys'."""
    if not SLUG_RE.match(slug):
        return []
    parts = slug.split("-")
    names = [" ".join(parts)]
    if len(parts) > 1:
        names.append(" ".join(parts[:-1]))
    return names


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
        self.businesses: list[str] = []
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
            business = (row.get("business") or "").strip()
            if business:
                dnc.businesses.append(business)
            if "email" in fields:
                dnc.emails.add(name_key(strip_mailto(row.get("email") or "")))
        dnc.emails.discard("")
        return dnc

    @staticmethod
    def _matches(candidate: str, entry: str) -> bool:
        """Conservative: exact key, prefix either way on the hint key, or on the core key."""
        if not candidate.strip():
            return False
        if name_key(candidate) == name_key(entry):
            return True
        if prefix_match(_hint_key(candidate), _hint_key(entry)):
            return True
        return prefix_match(_core_key(candidate), _core_key(entry))

    def reason(self, business_names: list[str], email: str = "") -> str | None:
        for entry in self.businesses:
            if any(self._matches(b, entry) for b in business_names):
                return f"business is on {DNC_LABEL} (matches {entry!r})"
        if email and name_key(strip_mailto(email)) in self.emails:
            return f"email is on {DNC_LABEL}"
        return None

    def mentioned_in(self, text: str) -> str | None:
        """For unparseable lines: any listed email token, or a listed name as a substring."""
        for token in EMAIL_TOKEN_RE.findall(text):
            if name_key(strip_mailto(token)) in self.emails:
                return f"mentions an email on {DNC_LABEL}"
        hay = _hint_key(text)
        for entry in self.businesses:
            for key in (_hint_key(entry), _core_key(entry)):
                if len(key) >= MIN_PREFIX and key in hay:
                    return f"mentions {entry!r} from {DNC_LABEL}"
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
        blocked = dnc.reason([m["business"], *slug_names(m["slug"])])
        if blocked:
            report.warn(W_DNC_LEGACY, f"{where}: {blocked}", S_LEGACY)
        if prospects is not None:
            check_against_prospects(
                [m["business"]], f"{m['business']} (slug {m['slug']})", where,
                prospects, by_key, report, S_LEGACY,
            )


def queue_date(path: Path) -> dt.date | None:
    m = QUEUE_FILE_RE.match(path.name)
    if not m or not QUEUE_DATE_RE.match(m.group(1)):
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def queue_files(
    outreach_dir: Path, today: dt.date, all_queues: bool, report: Report
) -> tuple[list[Path], list[Path]]:
    """Return (selected, past): selected = dated today or later (all with --all-queues)
    plus undated queue-*.txt; past = earlier-dated files, loaded read-only for re-queue checks.
    Queue file names are matched case-insensitively."""
    selected: list[Path] = []
    past: list[Path] = []
    if not outreach_dir.is_dir():
        return selected, past
    for path in sorted((p for p in outreach_dir.iterdir() if p.is_file()), key=lambda p: p.name.casefold()):
        if not QUEUE_FILE_RE.match(path.name):
            if "queue" in path.name.casefold() and path.name.casefold() not in QUEUE_DOCS:
                report.warn(W_QUEUE_LIKE, f"outreach/{path.name}", S_LIVE)
            continue
        date = queue_date(path)
        if date is None:
            report.warn(W_UNDATED, f"outreach/{path.name}", S_LIVE)
            selected.append(path)
        elif all_queues or date >= today:
            selected.append(path)
        else:
            past.append(path)
    return selected, past


def parse_queue_line(line: str) -> tuple[str, str] | None:
    """Return (first_field, business) or None if the line is malformed."""
    fields = [f.strip() for f in line.split("|")]
    if len(fields) < 2 or not fields[0] or not fields[1]:
        return None
    return fields[0], fields[1]


class QueueState:
    """Cross-file state for live queue checks (duplicates span ALL selected files)."""

    def __init__(self, prospects: list[dict[str, str]] | None, dnc: DoNotContact) -> None:
        self.prospects = prospects
        self.by_key = index_prospects(prospects)
        self.dnc = dnc
        self.dropped = [p["business_name"] for p in prospects or [] if p["priority"] == "drop"]
        self.emails: dict[str, list[str]] = defaultdict(list)
        self.businesses: dict[str, list[str]] = defaultdict(list)
        self.past_emails: dict[str, list[str]] = defaultdict(list)  # email -> ["date (file:line)"]


def queue_entries(text: str):
    """Yield (lineno, stripped_line, parsed_or_None) for non-blank, non-# lines."""
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line and not line.startswith("#"):
            yield lineno, line, parse_queue_line(line)


def load_past_queue(path: Path, state: QueueState) -> None:
    """Read-only scan of an earlier-dated queue file to detect email re-queues."""
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    date = queue_date(path)
    for lineno, _line, parsed in queue_entries(text):
        if parsed and "@" in parsed[0]:
            state.past_emails[name_key(strip_mailto(parsed[0]))].append(
                f"{date} (outreach/{path.name}:{lineno})"
            )


def check_malformed_line(where: str, line: str, state: QueueState, report: Report) -> None:
    """An unparseable line still gets the send-safety scan before it is only warned about."""
    hit = state.dnc.mentioned_in(line)
    if not hit:
        hay = _hint_key(line)
        for name in state.dropped:
            key = _hint_key(TRAILING_PAREN_RE.sub("", name) or name)
            if len(key) >= MIN_PREFIX and key in hay:
                hit = f"mentions dropped prospect {name!r}"
                break
    if hit:
        report.error(f"{where}: malformed queue line {hit}: {line[:80]!r}", S_LIVE)
    else:
        report.warn(W_MALFORMED, f"{where}: {line[:80]!r}", S_LIVE)


def check_live_queue(path: Path, state: QueueState, report: Report) -> int:
    """Check one selected queue file; return the number of entries parsed."""
    label = f"outreach/{path.name}"
    text = read_text(path, label, report, S_LIVE)
    if text is None:
        return 0
    entries = 0
    for lineno, line, parsed in queue_entries(text):
        where = f"{label}:{lineno}"
        if parsed is None:
            check_malformed_line(where, line, state, report)
            continue
        entries += 1
        first, business = parsed
        first = strip_mailto(first)
        bare = TRAILING_PAREN_RE.sub("", business) or business
        names = [business] if bare == business else [business, bare]
        where = f"{where} ({business})"
        is_email = "@" in first
        if is_email and not EMAIL_RE.match(first):
            report.warn(W_EMAIL, f"{where}: {first!r}", S_LIVE)
        elif not is_email and not SLUG_RE.match(first):
            report.warn(W_EMAIL, f"{where}: {first!r} is neither an email nor a slug", S_LIVE)
        if is_email:
            email_key = name_key(first)
            state.emails[email_key].append(where)
            for earlier in state.past_emails.get(email_key, []):
                report.warn(W_REQUEUE, f"{where}: {first!r} previously queued on {earlier}", S_LIVE)
        state.businesses[name_key(bare)].append(where)
        blocked = state.dnc.reason(names + ([] if is_email else slug_names(first)),
                                   first if is_email else "")
        if blocked:
            report.error(f"{where}: {blocked}", S_LIVE)
        if state.prospects is not None:
            check_against_prospects(names, f"{business} [{label}:{lineno}]", where,
                                    state.prospects, state.by_key, report, S_LIVE)
    return entries


def report_live_duplicates(state: QueueState, report: Report) -> None:
    for kind, seen in (("email", state.emails), ("business", state.businesses)):
        for key, places in seen.items():
            if len(places) > 1:
                report.error(
                    f"duplicate {kind} {key!r} queued {len(places)}x: " + "; ".join(places), S_LIVE
                )


def check_drafts(outreach_dir: Path, report: Report) -> list[Path]:
    """Every draft must carry the opt-out line. Only the DRAFT_EXEMPT docs are skipped."""
    drafts = [
        d for d in sorted(outreach_dir.glob("*.md")) if d.name not in DRAFT_EXEMPT
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

    live, past = queue_files(outreach_dir, today, all_queues, report)
    state = QueueState(prospects, dnc)
    for p in past:
        load_past_queue(p, state)
    live_entries = sum(check_live_queue(p, state, report) for p in live)
    report_live_duplicates(state, report)

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
