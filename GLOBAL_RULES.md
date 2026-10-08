# Global Rules — cortese-prospects

Loaded in EVERY agent session (builder, validator, triage). Keep it short.
Project instructions in `AGENTS.md` still apply; this file adds factory specifics.

## What this repo is
A sales-pipeline **data + content** repo for Cortese Digital's busy-line /
missed-call recovery offer for independent restaurants. There is no
application code, no package manifest, no build, and no CI. Validation is a
stdlib Python checker (`scripts/validate.py`) with a unittest suite (`tests/`).
Changes are mostly to CSV data, queue text files and Markdown documents.

## Repo layout (verified 2026-10-08 — re-list before relying on it)
- `prospects.csv` — lead list, one row per location. Header (12 columns, in order):
  `business_name,category,town,region,phone,website,online_ordering,call_volume_indicator,chain_or_independent,source_url,priority,pitch_angle`
- `outreach/*.md` — one email draft per prospect (`<slug>.md`; a few are `draft-<slug>.md`).
  `outreach/README*.md` files are docs, not drafts (see `outreach/README-QUEUE.md`).
- `outreach/queue-YYYY-MM-DD.txt` — the **live send queue**, one file per send date. One entry
  per line: `email | Business (Location) | source note | status note`; `#` lines are headers.
  The first field may be a slug (or `mailto:` email) while the email is still being found.
  File names are matched case-insensitively. The same email or business queued twice across
  the checked files is a hard error.
- `outreach/do_not_contact.csv` — `business,email,reason,added`. Matching is conservative
  (normalized name, prefix either way, generic words like "pizza"/"restaurant" ignored, slug,
  email). A live queue hit is a hard error; on the legacy manifest it is a named warning.
  Only Stephen adds rows.
- `outreach/manifest.csv` — **legacy** send queue (not sent from; last updated 2026-10-06).
  Header: `slug,business,email_draft_file,status(queued)`. Don't delete or reorder its rows.
- `scripts/validate.py` — the validator. `tests/test_validate.py` + `tests/fixtures/` — its tests.
- `README.md` — thesis, territory, sourcing/verification doctrine, data caveats, legal & conduct rules.
- `OUTREACH.md` — sales kit (offer, scripts, objections, billing).
- `PLAYBOOK.md` — per-customer onboarding checklist.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md` — agent instruction files.
- Factory files: `GLOBAL_RULES.md`, `FACTORY_RULES.md`, `mission.md`.
- **Never guess a path.** Run `git ls-files` (or `ls`) before referencing a file.

## Commands
- Runtime available: `python3` (3.13 on the factory box). Use the standard library only
  unless a spec explicitly justifies a dependency.
- Validation (run from the repo root; standard library only, no network):
  - `python3 scripts/validate.py` — must exit 0 before any data commit. Exits 1 only on
    hard failures; data-quality warnings are printed, grouped by section (live queue,
    legacy manifest, prospects/drafts/docs) with counts. By default it checks live queue
    files dated today or later (box local date).
  - `python3 scripts/validate.py --all-queues` — also checks past-dated queue files (then a
    re-queued email across dates is a hard duplicate; by default it is a warning).
  - `python3 scripts/validate.py --strict` — full check: warnings also fail. Expected to
    fail until the ticket-1 S2–S4 cleanup lands; its output is the cleanup backlog.
  - `python3 -m unittest discover -s tests -v` — validator tests. Includes a smoke test
    against the real repo data, so a data commit that adds a hard failure breaks this suite.

## Data rules (from README verification doctrine)
- Every `prospects.csv` row must keep a `source_url`. Never invent or "fix" phone
  digits, emails, addresses, or URLs from memory — only from a cited public source.
- Unverifiable rows are dropped or flagged, never guessed.
- Closed / disqualified leads are marked `priority=drop` with a bracketed reason in `pitch_angle`;
  do not silently delete rows (history matters for "never re-touch").
- No private data, nothing gathered behind a login. Public business info only.
- Never commit secrets, credentials, API keys, or private customer data.

## Git discipline
- Branch per issue: `factory/<issue-number>-<slug>`. Never commit directly to `main`.
- Small, focused commits with descriptive messages. No force-push.
- Other agents and Stephen commit to `main` frequently: rebase/merge from `origin/main`
  before opening a PR, and never rewrite their history.

## Style
- Match existing conventions (CSV column order, slug style `<business>-<town>`, draft
  structure ending with the `reply STOP to opt out` signature line).
- Smallest change that satisfies the spec. No reformatting of untouched rows/files.
