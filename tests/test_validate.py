"""Tests for scripts/validate.py. Run: python3 -m unittest discover -s tests -v"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_TODAY = "2026-01-01"  # the valid fixture's live queue file is queue-2026-01-01.txt

_spec = importlib.util.spec_from_file_location("validate", ROOT / "scripts" / "validate.py")
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)


def run(repo: Path, *extra: str, today: str | None = FIXTURE_TODAY) -> tuple[int, str]:
    args = ["--repo", str(repo), *extra]
    if today:
        args += ["--today", today]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = validate.main(args)
    return code, buf.getvalue()


class FixtureCase(unittest.TestCase):
    """Copies a fixture repo to a temp dir so each test can mutate it safely."""

    fixture = "valid"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        shutil.copytree(FIXTURES / self.fixture, self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def edit(self, rel: str, old: str, new: str) -> None:
        path = self.repo / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"fixture {rel} lacks {old!r}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def append(self, rel: str, line: str) -> None:
        with (self.repo / rel).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def assertHardFailure(self, *needles: str) -> str:
        code, out = run(self.repo)
        self.assertEqual(code, 1, out)
        self.assertIn("ERRORS (", out)
        for n in needles:
            self.assertIn(n, out)
        return out


class ValidFixtureTest(FixtureCase):
    def test_clean_fixture_passes_with_summary(self) -> None:
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "checked 3 prospects, 2 drafts, 2 live queue entries in 1 file, "
            "2 legacy manifest rows: 0 errors, 0 warnings",
            out,
        )
        self.assertIn("live queue files checked (dated 2026-01-01 or later): queue-2026-01-01.txt", out)
        self.assertNotIn("ERRORS", out)
        self.assertNotIn("WARNINGS", out)

    def test_strict_also_passes_when_clean(self) -> None:
        self.assertEqual(run(self.repo, "--strict")[0], 0)


class HardFailureTest(FixtureCase):
    def test_wrong_column_count_reports_file_and_line(self) -> None:
        self.edit("prospects.csv", "alpha.example,no,high,", "alpha.example,no,")
        self.assertHardFailure("prospects.csv line 2", "11 fields, expected 12")

    def test_bad_prospects_header(self) -> None:
        self.edit("prospects.csv", "business_name,", "name,")
        self.assertHardFailure("prospects.csv: header")

    def test_missing_prospects_file(self) -> None:
        (self.repo / "prospects.csv").unlink()
        self.assertHardFailure("prospects.csv: file not found")

    def test_empty_source_url_names_business(self) -> None:
        self.edit("prospects.csv", "https://alpha.example/", "")
        self.assertHardFailure("(Alpha Pizza): empty source_url")

    def test_non_http_source_url(self) -> None:
        self.edit("prospects.csv", "https://alpha.example/", "alpha.example")
        self.assertHardFailure("(Alpha Pizza): source_url is not an http(s) URL")

    def test_empty_phone(self) -> None:
        self.edit("prospects.csv", "(555) 010-0001", "")
        self.assertHardFailure("(Alpha Pizza): empty phone")

    def test_priority_outside_documented_set(self) -> None:
        self.edit("prospects.csv", "https://alpha.example/,A,", "https://alpha.example/,maybe,")
        self.assertHardFailure("(Alpha Pizza): priority 'maybe'")

    def test_documented_priorities_pass(self) -> None:
        for value in ("B", "C"):
            self.edit("prospects.csv", "https://alpha.example/,A,", f"https://alpha.example/,{value},")
            self.assertEqual(run(self.repo)[0], 0)
            self.edit("prospects.csv", f"https://alpha.example/,{value},", "https://alpha.example/,A,")

    def test_manifest_points_at_missing_draft(self) -> None:
        (self.repo / "outreach" / "beta-testville.md").unlink()
        self.assertHardFailure("draft outreach/beta-testville.md does not exist")

    def test_manifest_draft_must_be_bare_filename(self) -> None:
        self.edit("outreach/manifest.csv", ",beta-testville.md,", ",../beta-testville.md,")
        self.assertHardFailure("must be a bare filename")

    def test_duplicate_slug_in_queue(self) -> None:
        self.append("outreach/manifest.csv", "alpha-testville,Alpha Pizza Again,alpha-testville.md,queued")
        self.assertHardFailure("duplicate slug 'alpha-testville'")

    def test_duplicate_business_in_queue(self) -> None:
        self.append("outreach/manifest.csv", "alpha-two,Alpha Pizza,alpha-testville.md,queued")
        self.assertHardFailure("duplicate business 'Alpha Pizza'")

    def test_bad_manifest_row_length(self) -> None:
        self.append("outreach/manifest.csv", "only,three,fields")
        self.assertHardFailure("outreach/manifest.csv line 4: 3 fields, expected 4")

    def test_draft_missing_opt_out_line(self) -> None:
        self.edit("outreach/alpha-testville.md", " · reply STOP to opt out", "")
        self.assertHardFailure("outreach/alpha-testville.md: missing opt-out line")

    def test_restoring_opt_out_line_passes_again(self) -> None:
        self.edit("outreach/alpha-testville.md", " · reply STOP to opt out", "")
        self.edit("outreach/alpha-testville.md", "Binghamton, NY", "Binghamton, NY · reply STOP to opt out")
        self.assertEqual(run(self.repo)[0], 0)

    def test_unqueued_draft_without_opt_out_still_fails(self) -> None:
        (self.repo / "outreach" / "loose.md").write_text("Subject: no opt-out\n", encoding="utf-8")
        self.assertHardFailure("outreach/loose.md: missing opt-out line")

    def test_queued_business_marked_drop(self) -> None:
        shutil.copy(self.repo / "outreach" / "alpha-testville.md", self.repo / "outreach" / "gamma-testville.md")
        self.append("outreach/manifest.csv", "gamma-testville,Gamma Diner,gamma-testville.md,queued")
        self.assertHardFailure("(Gamma Diner): queued business is marked priority=drop")

    def test_do_not_contact_on_legacy_manifest_is_warning(self) -> None:
        # Gamma Diner is drop in prospects but not queued anywhere live; use a manifest-only name.
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,email,reason,added\nZeta Grill,,closed,2026-10-08\n", encoding="utf-8"
        )
        shutil.copy(self.repo / "outreach" / "alpha-testville.md", self.repo / "outreach" / "zeta.md")
        self.append("outreach/manifest.csv", "zeta-testville,Zeta Grill,zeta.md,queued")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(validate.S_LEGACY + ":", out)
        self.assertIn(f"[1] {validate.W_DNC_LEGACY}:", out)
        self.assertIn("(Zeta Grill): business is on outreach/do_not_contact.csv", out)

    def test_do_not_contact_blocks_live_queue_business(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,email,reason,added\nBeta Wings,,STOP reply,2026-10-01\n", encoding="utf-8"
        )
        self.assertHardFailure(
            "outreach/queue-2026-01-01.txt:3 (Beta Wings (Testville)): business is on outreach/do_not_contact.csv"
        )

    def test_do_not_contact_list_absent_is_fine(self) -> None:
        self.assertFalse((self.repo / "outreach" / "do_not_contact.csv").exists())
        self.assertEqual(run(self.repo)[0], 0)


class NameNormalizationTest(FixtureCase):
    """Drop/duplicate/do-not-contact checks must not be bypassed by name variants."""

    def queue(self, business: str, slug: str = "gamma-testville") -> None:
        shutil.copy(self.repo / "outreach" / "alpha-testville.md", self.repo / "outreach" / f"{slug}.md")
        self.append("outreach/manifest.csv", f"{slug},{business},{slug}.md,queued")

    def test_drop_check_ignores_trailing_space(self) -> None:
        self.queue("Gamma Diner ")
        self.assertHardFailure("(Gamma Diner ): queued business is marked priority=drop")

    def test_drop_check_ignores_capitalization(self) -> None:
        self.queue("gamma DINER")
        self.assertHardFailure("(gamma DINER): queued business is marked priority=drop")

    def test_drop_check_collapses_internal_whitespace(self) -> None:
        self.queue("Gamma   Diner")
        self.assertHardFailure("(Gamma   Diner): queued business is marked priority=drop")

    def test_near_match_to_drop_row_is_hard_error(self) -> None:
        self.queue("Gamma Diners of Testville")
        out = self.assertHardFailure("queued business near-matches a dropped prospect: Gamma Diner (line 4)")
        self.assertNotIn(validate.W_ORPHAN, out)

    def test_location_suffix_on_legacy_manifest_matches_drop_row(self) -> None:
        self.queue("Gamma Diner (Testville)")
        self.assertHardFailure("(Gamma Diner (Testville)): queued business is marked priority=drop")

    def test_near_match_with_suffix_to_drop_row_is_hard_error(self) -> None:
        self.queue("Gamma Diner of Testville")
        self.assertHardFailure("(Gamma Diner of Testville): queued business near-matches a dropped prospect")

    def test_near_match_to_active_row_stays_warning(self) -> None:
        self.queue("Alpha Pizza of Testville", slug="alpha-two")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("Alpha Pizza of Testville (slug alpha-two) — possible near-match, verify: Alpha Pizza", out)

    def test_location_suffix_on_legacy_manifest_matches_active_row(self) -> None:
        self.queue("Alpha Pizza (Testville)", slug="alpha-two")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn(validate.W_ORPHAN, out)

    def test_duplicate_business_case_variant(self) -> None:
        self.queue("alpha  PIZZA ", slug="alpha-two")
        self.assertHardFailure("duplicate business 'Alpha Pizza', 'alpha  PIZZA ' (2 rows)")

    def test_duplicate_slug_case_variant(self) -> None:
        self.queue("Alpha Pizza Two", slug="ALPHA-TESTVILLE")
        self.assertHardFailure("duplicate slug 'alpha-testville', 'ALPHA-TESTVILLE' (2 rows)")

    def test_do_not_contact_matches_normalized_names(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,email,reason,added\n  BETA   wings ,,STOP reply,2026-10-01\n", encoding="utf-8"
        )
        self.assertHardFailure("(Beta Wings (Testville)): business is on outreach/do_not_contact.csv")

    def test_do_not_contact_matches_queue_variant(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,email,reason,added\nAlpha Pizza,,STOP reply,2026-10-01\n", encoding="utf-8"
        )
        self.edit("outreach/queue-2026-01-01.txt", "| Alpha Pizza (Testville NY) |", "| ALPHA   pizza  |")
        self.assertHardFailure("(ALPHA   pizza): business is on outreach/do_not_contact.csv")

    def test_do_not_contact_legacy_manifest_variant_is_named(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,email,reason,added\nZeta Grill,,STOP reply,2026-10-01\n", encoding="utf-8"
        )
        shutil.copy(self.repo / "outreach" / "alpha-testville.md", self.repo / "outreach" / "zeta.md")
        self.append("outreach/manifest.csv", "zeta-testville, ZETA grill ,zeta.md,queued")
        out = run(self.repo)[1]
        self.assertIn("( ZETA grill ): business is on outreach/do_not_contact.csv", out)


class EncodingAndStatusTest(FixtureCase):
    def corrupt(self, rel: str) -> int:
        """Insert an invalid UTF-8 byte after the first line; return its byte offset."""
        path = self.repo / rel
        data = path.read_bytes()
        offset = data.index(b"\n") + 1
        path.write_bytes(data[:offset] + b"\xff" + data[offset:])
        return offset

    def test_non_utf8_prospects_is_hard_error_not_traceback(self) -> None:
        offset = self.corrupt("prospects.csv")
        out = self.assertHardFailure(f"prospects.csv: not valid UTF-8 (byte {offset})")
        self.assertNotIn("Traceback", out)

    def test_non_utf8_manifest_is_hard_error(self) -> None:
        offset = self.corrupt("outreach/manifest.csv")
        self.assertHardFailure(f"outreach/manifest.csv: not valid UTF-8 (byte {offset})")

    def test_non_utf8_draft_is_hard_error(self) -> None:
        offset = self.corrupt("outreach/beta-testville.md")
        self.assertHardFailure(f"outreach/beta-testville.md: not valid UTF-8 (byte {offset})")

    def test_non_utf8_queue_file_is_hard_error(self) -> None:
        offset = self.corrupt("outreach/queue-2026-01-01.txt")
        out = self.assertHardFailure(f"outreach/queue-2026-01-01.txt: not valid UTF-8 (byte {offset})")
        self.assertNotIn("Traceback", out)

    def test_non_utf8_do_not_contact_is_hard_error(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_bytes(b"business\n\xffBeta Wings\n")
        self.assertHardFailure("outreach/do_not_contact.csv: not valid UTF-8 (byte 9)")

    def test_byte_order_mark_is_accepted(self) -> None:
        for rel in ("prospects.csv", "outreach/manifest.csv", "outreach/alpha-testville.md"):
            path = self.repo / rel
            path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("0 errors, 0 warnings", out)

    def test_non_queued_status_is_warning(self) -> None:
        self.edit("outreach/manifest.csv", "beta-testville.md,queued", "beta-testville.md,sent")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(f"[1] {validate.W_STATUS}:", out)
        self.assertIn("(Beta Wings): status 'sent'", out)

    def test_opt_out_check_stays_case_sensitive(self) -> None:
        self.edit("outreach/alpha-testville.md", "reply STOP to opt out", "reply stop to opt out")
        self.assertHardFailure("outreach/alpha-testville.md: missing opt-out line")


class QueueHelpers(FixtureCase):
    """Helpers for live-queue tests (defines no tests itself)."""

    QUEUE = "outreach/queue-2026-01-01.txt"

    def add(self, line: str, rel: str = QUEUE) -> None:
        self.append(rel, line)

    def dnc(self, rows: str) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,email,reason,added\n" + rows, encoding="utf-8"
        )

    def add_prospect(self, name: str, priority: str = "B", town: str = "Testville") -> None:
        self.append(
            "prospects.csv",
            f"{name},pizza & takeout,{town},Test County NY,(555) 010-0009,,no,high,"
            f"independent,https://extra.example/,{priority},fixture row",
        )


class LiveQueueTest(QueueHelpers):
    """Dated outreach/queue-YYYY-MM-DD.txt files are the live send queue."""

    def test_comment_blank_and_slug_lines_are_tolerated(self) -> None:
        self.add("")
        self.add("# another comment | with | pipes")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("2 live queue entries in 1 file", out)

    def test_drop_row_with_location_suffix_is_hard_error(self) -> None:
        self.add("g@gamma.example | Gamma Diner (Testville NY) | footer | needs draft")
        self.assertHardFailure(
            "outreach/queue-2026-01-01.txt:4 (Gamma Diner (Testville NY)): "
            "queued business is marked priority=drop"
        )

    def test_drop_row_case_and_space_variant_is_hard_error(self) -> None:
        self.add("g@gamma.example |   gamma   DINER   | footer | needs draft")
        self.assertHardFailure("(gamma   DINER): queued business is marked priority=drop")

    def test_near_match_to_only_drop_row_is_hard_error(self) -> None:
        self.add("g@gamma.example | Gamma Diner of Testville (NY) | footer | needs draft")
        self.assertHardFailure("queued business near-matches a dropped prospect: Gamma Diner (line 4)")

    def test_near_match_to_drop_and_active_row_is_warning(self) -> None:
        self.add_prospect("Gamma Diner Express")
        self.add("g@gamma.example | Gamma Diner of Testville | footer | needs draft")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(
            "Gamma Diner of Testville [outreach/queue-2026-01-01.txt:4] — possible near-match, verify: "
            "Gamma Diner [drop]; Gamma Diner Express",
            out,
        )

    def test_legacy_near_match_to_drop_and_active_row_is_warning(self) -> None:
        self.add_prospect("Gamma Diner Express")
        shutil.copy(self.repo / "outreach" / "alpha-testville.md", self.repo / "outreach" / "g.md")
        self.append("outreach/manifest.csv", "gamma-of-testville,Gamma Diner of Testville,g.md,queued")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("possible near-match, verify: Gamma Diner [drop]; Gamma Diner Express", out)

    def test_accented_variant_of_drop_row_is_hard_error(self) -> None:
        self.add("g@gamma.example | Gâmma Dîner (Testville) | footer | needs draft")
        self.assertHardFailure("(Gâmma Dîner (Testville)): queued business is marked priority=drop")

    def test_accented_near_match_to_drop_row_is_hard_error(self) -> None:
        self.add("g@gamma.example | Gâmma Dînér of Testville | footer | needs draft")
        self.assertHardFailure("near-matches a dropped prospect: Gamma Diner (line 4)")

    def test_accents_fold_for_exact_match_to_active_row(self) -> None:
        self.add_prospect("Café Delta")
        self.add("d@delta.example | Cafe Delta (Testville) | footer | needs draft")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("Cafe Delta (Testville) [", out)

    def test_do_not_contact_email_match_is_hard_error(self) -> None:
        self.dnc("Someone Else,ALPHA@Alpha.Example ,STOP reply,2026-10-01\n")
        self.assertHardFailure("(Alpha Pizza (Testville NY)): email is on outreach/do_not_contact.csv")

    def test_do_not_contact_without_email_column_still_matches_business(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,reason\nAlpha Pizza,closed\n", encoding="utf-8"
        )
        self.assertHardFailure("(Alpha Pizza (Testville NY)): business is on outreach/do_not_contact.csv")

    def test_malformed_line_is_warning_with_file_and_line(self) -> None:
        self.add("just some text without pipes")
        self.add(" | Missing First Field | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(f"[2] {validate.W_MALFORMED}:", out)
        self.assertIn("outreach/queue-2026-01-01.txt:4: 'just some text without pipes'", out)
        self.assertIn("outreach/queue-2026-01-01.txt:5:", out)
        self.assertNotIn("Traceback", out)

    def test_malformed_email_is_warning(self) -> None:
        self.add("eps@@eps | Epsilon Subs | x | y")
        self.add("Not A Slug | Eta Subs | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(f"[2] {validate.W_EMAIL}:", out)
        self.assertIn("(Epsilon Subs): 'eps@@eps'", out)
        self.assertIn("'Not A Slug' is neither an email nor a slug", out)

    def test_duplicate_email_in_same_file_is_hard_error(self) -> None:
        self.add("ALPHA@alpha.example | Epsilon Subs | x | y")
        self.assertHardFailure("duplicate email 'alpha@alpha.example' queued 2x")

    def test_duplicate_business_in_same_file_is_hard_error(self) -> None:
        self.add("other@beta.example | BETA  wings (Testville NY) | x | y")
        self.assertHardFailure("duplicate business 'beta wings' at 'testville' queued 2x")

    def test_duplicate_across_selected_files_is_hard_error(self) -> None:
        (self.repo / "outreach" / "queue-2026-01-02.txt").write_text(
            "alpha@alpha.example | Alpha Pizza | x | y\n", encoding="utf-8"
        )
        out = self.assertHardFailure("duplicate email 'alpha@alpha.example' queued 2x")
        self.assertIn("duplicate business 'alpha pizza' queued 2x", out)
        self.assertIn("queue-2026-01-01.txt, queue-2026-01-02.txt", out)

    def test_mailto_variant_counts_as_duplicate(self) -> None:
        self.add("MAILTO:Alpha@Alpha.example | Epsilon Subs | x | y")
        self.assertHardFailure("duplicate email 'alpha@alpha.example' queued 2x")

    def test_requeue_of_past_email_warns_by_default(self) -> None:
        (self.repo / "outreach" / "queue-2025-12-31.txt").write_text(
            "# old\nalpha@alpha.example | Alpha Pizza | x | sent\n", encoding="utf-8"
        )
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(f"[1] {validate.W_REQUEUE}:", out)
        self.assertIn(
            "'alpha@alpha.example' previously queued on 2025-12-31 (outreach/queue-2025-12-31.txt:2)", out
        )
        self.assertNotIn("live queue files checked (dated 2026-01-01 or later): queue-2025-12-31", out)

    def test_requeue_of_past_email_is_hard_error_with_all_queues(self) -> None:
        (self.repo / "outreach" / "queue-2025-12-31.txt").write_text(
            "alpha@alpha.example | Alpha Pizza | x | sent\n", encoding="utf-8"
        )
        code, out = run(self.repo, "--all-queues")
        self.assertEqual(code, 1, out)
        self.assertIn("duplicate email 'alpha@alpha.example' queued 2x", out)

    def test_orphan_live_entry_is_named_warning_with_hint(self) -> None:
        self.add("z@zeta.example | Zeta Grill (Testville) | x | y")
        self.add("a@alpha.example | Alpha Pizzeria of Testville | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(validate.S_LIVE + ":", out)
        self.assertIn("Zeta Grill (Testville) [outreach/queue-2026-01-01.txt:4] — no similar name", out)
        self.assertIn(
            "Alpha Pizzeria of Testville [outreach/queue-2026-01-01.txt:5] — possible near-match, verify: Alpha Pizza",
            out,
        )

    def test_past_queue_skipped_by_default_checked_with_all_queues(self) -> None:
        (self.repo / "outreach" / "queue-2025-12-31.txt").write_text(
            "# old\ng@gamma.example | Gamma Diner (Testville) | x | sent\n", encoding="utf-8"
        )
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("queue-2025-12-31.txt", out)
        code, out = run(self.repo, "--all-queues")
        self.assertEqual(code, 1, out)
        self.assertIn("live queue files checked (all dates): queue-2025-12-31.txt, queue-2026-01-01.txt", out)
        self.assertIn("outreach/queue-2025-12-31.txt:2 (Gamma Diner (Testville)): queued business is marked", out)

    def test_future_queue_checked_by_default(self) -> None:
        self.assertEqual(run(self.repo, today="2025-06-01")[0], 0)
        out = run(self.repo, today="2026-01-02")[1]
        self.assertIn("live queue files checked (dated 2026-01-02 or later): none", out)

    def test_undated_queue_file_is_warned_and_checked(self) -> None:
        (self.repo / "outreach" / "queue-tomorrow.txt").write_text(
            "g@gamma.example | Gamma Diner | x | y\n", encoding="utf-8"
        )
        out = self.assertHardFailure("outreach/queue-tomorrow.txt:1 (Gamma Diner): queued business is marked")
        self.assertIn(f"[1] {validate.W_UNDATED}:", out)

    def test_readme_in_outreach_is_not_a_draft(self) -> None:
        (self.repo / "outreach" / "README-QUEUE.md").write_text("# Send queues\n", encoding="utf-8")
        (self.repo / "outreach" / "README.md").write_text("# Outreach\n", encoding="utf-8")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("2 drafts", out)
        self.assertNotIn(validate.W_QUEUE_LIKE, out)

    def test_other_readme_files_still_need_opt_out(self) -> None:
        (self.repo / "outreach" / "README-draft-notes.md").write_text("Subject: x\n", encoding="utf-8")
        self.assertHardFailure("outreach/README-draft-notes.md: missing opt-out line")


class ReviewFixesTest(QueueHelpers):
    """Cases from the PR #4 validator review."""

    def only_queue_line(self, line: str) -> None:
        (self.repo / "outreach" / "queue-2026-01-01.txt").write_text(
            "# fixture\n" + line + "\n", encoding="utf-8"
        )

    def test_do_not_contact_variants_are_hard_errors(self) -> None:
        self.dnc("Sharkey's Restaurant,,closed 2020,2026-10-08\nOpted Out Pizza,,STOP reply,2026-10-08\n")
        cases = [
            "s@sharkeys.example | Sharkey\u2019s Restaurant | x | y",
            "s@sharkeys.example | Sharkeys Restaurant | x | y",
            "s@sharkeys.example | Sharkey's (Binghamton) | x | y",
            "s@sharkeys.example | Sharkey's Bar & Grill (Binghamton) | x | y",
            "sharkeys-binghamton | Sharkeys (Binghamton) | x | y",
            "sharkeys-binghamton | Glenwood Spiedies (Binghamton) | x | y",
            "o@opted.example | Opted Out Pizzeria | x | y",
            "s@sharkeys.example | The Sharkey's Restaurant | x | y",
        ]
        for line in cases:
            with self.subTest(line=line):
                self.only_queue_line(line)
                code, out = run(self.repo)
                self.assertEqual(code, 1, out)
                self.assertIn("business is on outreach/do_not_contact.csv (matches", out)

    def test_do_not_contact_does_not_match_trivially_short_keys(self) -> None:
        self.dnc("Sal's Pizza,,closed,2026-10-08\n")
        self.only_queue_line("s@salvatore.example | Salvatore's Pizzeria (Testville) | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("do_not_contact.csv (matches", out)

    def test_malformed_line_with_do_not_contact_email_is_hard_error(self) -> None:
        self.dnc("Someone,stop@me.example,STOP reply,2026-10-08\n")
        self.add("resend later to mailto:STOP@me.example please")
        self.assertHardFailure("malformed queue line mentions an email on outreach/do_not_contact.csv")

    def test_malformed_line_with_do_not_contact_name_is_hard_error(self) -> None:
        self.dnc("Sharkey's Restaurant,,closed 2020,2026-10-08\n")
        self.add("Sharkey\u2019s Restaurant - call back Friday")
        self.assertHardFailure("malformed queue line mentions \"Sharkey's Restaurant\" from outreach/do_not_contact.csv")

    def test_malformed_line_with_dropped_name_is_hard_error(self) -> None:
        self.add("retry Gamma Diner after lunch")
        self.assertHardFailure("malformed queue line mentions dropped prospect 'Gamma Diner'")

    def test_curly_and_modifier_apostrophes_fold(self) -> None:
        for ch in ("\u2019", "\u2018", "\u02bc"):
            self.assertEqual(validate.name_key(f"Delta{ch}s Diner"), validate.name_key("Delta's Diner"))

    def test_curly_apostrophe_exact_matches_drop_row(self) -> None:
        self.add_prospect("Delta's Diner", priority="drop")
        self.add("d@delta.example | Delta\u2019s Diner (Testville) | x | y")
        self.assertHardFailure("(Delta\u2019s Diner (Testville)): queued business is marked priority=drop")

    def test_mailto_prefix_is_stripped_before_email_checks(self) -> None:
        self.add("mailto: eps@eps.example | Epsilon Subs | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn(validate.W_EMAIL, out)

    def test_mailto_prefix_matches_do_not_contact_email(self) -> None:
        self.dnc("Someone Else,Eps@eps.example,STOP reply,2026-10-08\nOther,mailto:z@z.example,x,2026-10-08\n")
        self.add("MAILTO:EPS@eps.example | Epsilon Subs | x | y")
        self.assertHardFailure("(Epsilon Subs): email is on outreach/do_not_contact.csv")
        self.only_queue_line("z@z.example | Zeta Grill | x | y")
        self.assertHardFailure("(Zeta Grill): email is on outreach/do_not_contact.csv")

    def test_queue_files_found_case_insensitively(self) -> None:
        (self.repo / "outreach" / "Queue-2026-01-02.TXT").write_text(
            "g@gamma.example | Gamma Diner | x | y\n", encoding="utf-8"
        )
        out = self.assertHardFailure("outreach/Queue-2026-01-02.TXT:1 (Gamma Diner): queued business is marked")
        self.assertIn("queue-2026-01-01.txt, Queue-2026-01-02.TXT", out)

    def test_other_queue_like_files_are_warned(self) -> None:
        for name in ("queue_2026-01-02.txt", "send-QUEUE.csv"):
            (self.repo / "outreach" / name).write_text("x\n", encoding="utf-8")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(f"[2] {validate.W_QUEUE_LIKE}:", out)
        self.assertIn("outreach/queue_2026-01-02.txt", out)
        self.assertIn("outreach/send-QUEUE.csv", out)

    def test_short_prefix_of_dropped_name_is_hard_error(self) -> None:
        self.add("g@gamma.example | Gamma (Testville) | x | y")
        self.assertHardFailure("(Gamma (Testville)): queued business near-matches a dropped prospect: Gamma Diner")

    def test_leading_the_is_ignored(self) -> None:
        self.add("g@gamma.example | The Gamma Diner (Testville) | x | y")
        self.assertHardFailure("(The Gamma Diner (Testville)): queued business is marked priority=drop")

    def test_prefix_near_match_with_active_row_stays_warning(self) -> None:
        self.add_prospect("Gamma Grill")
        self.add("g@gamma.example | Gamma (Testville) | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("possible near-match, verify: Gamma Diner [drop]; Gamma Grill", out)

    def test_middle_word_variant_is_a_documented_gap(self) -> None:
        # Known limitation: an inserted middle word defeats prefix near-matching. It is
        # still surfaced as an orphan warning, not silently accepted.
        self.add("g@gamma.example | Gamma Italian Diner | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("Gamma Italian Diner [outreach/queue-2026-01-01.txt:4] — no similar name", out)



class LocationAwareTest(QueueHelpers):
    """Same bare name in different towns: duplicates, prospect rows and do-not-contact."""

    def hometown_rows(self, canastota: str = "B", groton: str = "A") -> None:
        self.add_prospect("Hometown Pizzeria", priority=canastota, town="Canastota")
        self.add_prospect("Hometown Pizzeria (Groton)", priority=groton, town="Groton")

    def test_same_name_different_towns_is_not_duplicate(self) -> None:
        self.hometown_rows()
        self.add("h1@hometown.example | Hometown Pizzeria (Canastota) | x | y")
        self.add("h2@hometown.example | Hometown Pizzeria (Groton NY) | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("duplicate", out)
        self.assertNotIn("Hometown Pizzeria (", out.split("WARNINGS")[-1] if "WARNINGS" in out else "")

    def test_branch_locations_with_separate_emails_are_not_duplicate(self) -> None:
        self.add_prospect("Nirchi's Pizza (Downtown)", town="Binghamton")
        self.add_prospect("Nirchi's Pizza (Upper Front St)", town="Binghamton")
        self.add("n1@nirchis.example | Nirchi's Pizza (Downtown) | x | y")
        self.add("n2@nirchis.example | Nirchi's Pizza (Upper Front St) | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("duplicate", out)
        self.assertNotIn(validate.W_ORPHAN, out)

    def test_same_town_spelled_differently_is_duplicate(self) -> None:
        self.add("j1@joeys.example | Joey's Pizza (Dunmore PA) | x | y")
        self.add("j2@joeys.example | Joey's Pizza (Dunmore) | x | y")
        self.assertHardFailure("duplicate business \"joey's pizza\" at 'dunmore' queued 2x")

    def test_same_email_in_different_towns_is_still_duplicate(self) -> None:
        self.add("h@hometown.example | Hometown Pizzeria (Canastota) | x | y")
        self.add("h@hometown.example | Hometown Pizzeria (Groton) | x | y")
        out = self.assertHardFailure("duplicate email 'h@hometown.example' queued 2x")
        self.assertNotIn("duplicate business", out)

    def test_location_picks_the_dropped_row(self) -> None:
        self.hometown_rows(canastota="drop", groton="A")
        self.add("h@hometown.example | Hometown Pizzeria (Canastota) | x | y")
        self.assertHardFailure("(Hometown Pizzeria (Canastota)): queued business is marked priority=drop")

    def test_location_picks_the_active_row(self) -> None:
        self.hometown_rows(canastota="drop", groton="A")
        self.add("h@hometown.example | Hometown Pizzeria (Groton NY) | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("Hometown", out)

    def test_unknown_location_falls_back_to_all_rows(self) -> None:
        self.hometown_rows(canastota="drop", groton="A")
        self.add("h@hometown.example | Hometown Pizzeria (Ithaca) | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("Hometown", out)

    def test_unknown_location_with_all_rows_dropped_is_hard_error(self) -> None:
        self.hometown_rows(canastota="drop", groton="drop")
        self.add("h@hometown.example | Hometown Pizzeria (Ithaca) | x | y")
        self.assertHardFailure("(Hometown Pizzeria (Ithaca)): queued business is marked priority=drop")

    def test_town_scoped_do_not_contact_spares_other_towns(self) -> None:
        self.dnc_town("Joey's Pizza,,Dunmore,closed,2026-10-08\n")
        self.add("j@joeysrome.example | Joey's Pizzeria (Rome) | x | y")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("do_not_contact.csv (matches", out)

    def test_town_scoped_do_not_contact_blocks_its_town(self) -> None:
        self.dnc_town("Joey's Pizza,,Dunmore,closed,2026-10-08\n")
        self.add("j@joeys.example | Joey's Pizza (Dunmore PA) | x | y")
        self.assertHardFailure(
            "(Joey's Pizza (Dunmore PA)): business is on outreach/do_not_contact.csv "
            "(matches \"Joey's Pizza\", town 'dunmore')"
        )

    def test_town_scoped_do_not_contact_blocks_entry_without_location(self) -> None:
        self.dnc_town("Joey's Pizza,,Dunmore,closed,2026-10-08\n")
        self.add("j@joeys.example | Joey's Pizzeria | x | y")
        self.assertHardFailure("(Joey's Pizzeria): business is on outreach/do_not_contact.csv")

    def test_town_scoped_do_not_contact_email_blocks_anywhere(self) -> None:
        self.dnc_town("Joey's Pizza,j@joeys.example,Dunmore,STOP reply,2026-10-08\n")
        self.add("j@joeys.example | Joey's Pizzeria (Rome) | x | y")
        self.assertHardFailure("(Joey's Pizzeria (Rome)): email is on outreach/do_not_contact.csv")

    def test_empty_town_keeps_broad_matching(self) -> None:
        self.dnc_town("Joey's Pizza,,,closed,2026-10-08\n")
        self.add("j@joeysrome.example | Joey's Pizzeria (Rome) | x | y")
        self.assertHardFailure("(Joey's Pizzeria (Rome)): business is on outreach/do_not_contact.csv")

    def test_past_business_requeue_warns(self) -> None:
        (self.repo / "outreach" / "queue-2025-12-31.txt").write_text(
            "old@alpha.example | Alpha Pizza (Testville) | x | sent\n", encoding="utf-8"
        )
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn(f"[1] {validate.W_REQUEUE}:", out)
        self.assertIn(
            "business 'alpha pizza' previously queued on 2025-12-31 (outreach/queue-2025-12-31.txt:1)", out
        )

    def test_past_business_in_other_town_does_not_warn(self) -> None:
        (self.repo / "outreach" / "queue-2025-12-31.txt").write_text(
            "old@alpha.example | Alpha Pizza (Elsewhere) | x | sent\n", encoding="utf-8"
        )
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn(validate.W_REQUEUE, out)

    def dnc_town(self, rows: str) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,email,town,reason,added\n" + rows, encoding="utf-8"
        )


class WarningFixtureTest(FixtureCase):
    fixture = "warnings"

    def test_warnings_do_not_fail_by_default(self) -> None:
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("ERRORS", out)
        self.assertIn("WARNINGS (6):", out)
        self.assertIn("0 errors, 6 warnings", out)

    def test_warnings_are_grouped_with_counts(self) -> None:
        out = run(self.repo)[1]
        self.assertIn(f"[2] {validate.W_ORPHAN}:", out)
        self.assertIn(f"[1] {validate.W_PHONE}:", out)
        self.assertIn(f"[2] {validate.W_VOCAB}:", out)
        self.assertIn(f"[1] {validate.W_README}:", out)

    def test_orphans_are_named_with_hints(self) -> None:
        out = run(self.repo)[1]
        self.assertIn(
            "Alpha Pizzeria of Testville (slug alpha-pizzeria-testville) — possible near-match, verify: Alpha Pizza",
            out,
        )
        self.assertIn("Closed Tavern (slug closed-testville) — no similar name", out)

    def test_specific_warning_details(self) -> None:
        out = run(self.repo)[1]
        self.assertIn("(Alpha Pizza): '555-010-0001'", out)
        self.assertIn("online_ordering='yes (ChowNOW)'", out)
        self.assertIn("README says 54 verified leads; prospects.csv has 2 non-drop rows", out)

    def test_strict_turns_warnings_into_failure(self) -> None:
        code, out = run(self.repo, "--strict")
        self.assertEqual(code, 1)
        self.assertIn("treated as errors: --strict", out)


class RealRepoSmokeTest(unittest.TestCase):
    """The real data must have no hard failures (warnings are expected until S2)."""

    def test_real_repo_has_no_hard_failures(self) -> None:
        code, out = run(ROOT)
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
