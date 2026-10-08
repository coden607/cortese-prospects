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

_spec = importlib.util.spec_from_file_location("validate", ROOT / "scripts" / "validate.py")
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)


def run(repo: Path, *extra: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = validate.main(["--repo", str(repo), *extra])
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
        self.assertIn("checked 3 prospects, 2 drafts, 2 queued: 0 errors, 0 warnings", out)
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

    def test_do_not_contact_list_blocks_queued_business(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,town,reason,date\nBeta Wings,Testville,STOP reply,2026-10-01\n", encoding="utf-8"
        )
        self.assertHardFailure("(Beta Wings): business is on outreach/do_not_contact.csv")

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
        self.queue("Gamma Diner (Testville)")
        out = self.assertHardFailure("queued business near-matches a dropped prospect: Gamma Diner (line 4)")
        self.assertNotIn(validate.W_ORPHAN, out)

    def test_near_match_with_suffix_to_drop_row_is_hard_error(self) -> None:
        self.queue("Gamma Diner of Testville")
        self.assertHardFailure("(Gamma Diner of Testville): queued business near-matches a dropped prospect")

    def test_near_match_to_active_row_stays_warning(self) -> None:
        self.queue("Alpha Pizza (Testville)", slug="alpha-two")
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("Alpha Pizza (Testville) (slug alpha-two) — possible near-match, verify: Alpha Pizza", out)

    def test_duplicate_business_case_variant(self) -> None:
        self.queue("alpha  PIZZA ", slug="alpha-two")
        self.assertHardFailure("duplicate business 'Alpha Pizza', 'alpha  PIZZA ' (2 rows)")

    def test_duplicate_slug_case_variant(self) -> None:
        self.queue("Alpha Pizza Two", slug="ALPHA-TESTVILLE")
        self.assertHardFailure("duplicate slug 'alpha-testville', 'ALPHA-TESTVILLE' (2 rows)")

    def test_do_not_contact_matches_normalized_names(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,town,reason,date\n  BETA   wings ,Testville,STOP reply,2026-10-01\n", encoding="utf-8"
        )
        self.assertHardFailure("(Beta Wings): business is on outreach/do_not_contact.csv")

    def test_do_not_contact_matches_queue_variant(self) -> None:
        (self.repo / "outreach" / "do_not_contact.csv").write_text(
            "business,town,reason,date\nAlpha Pizza,Testville,STOP reply,2026-10-01\n", encoding="utf-8"
        )
        self.edit("outreach/manifest.csv", "alpha-testville,Alpha Pizza,", "alpha-testville,ALPHA pizza ,")
        self.assertHardFailure("(ALPHA pizza ): business is on outreach/do_not_contact.csv")


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
