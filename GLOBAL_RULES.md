# Global Rules — cortese-prospects

Loaded in EVERY agent session (builder, validator, triage). Keep it short.
Project instructions in `AGENTS.md` still apply; this file adds factory specifics.

## What this repo is
A sales-pipeline **data + content** repo for Cortese Digital's busy-line /
missed-call recovery offer for independent restaurants. There is no
application code, no package manifest, no build, and (as of 2026-10-07) no
test suite or CI. Changes are to CSV data and Markdown documents.

## Repo layout (verified 2026-10-07 — re-list before relying on it)
- `prospects.csv` — lead list, one row per location. Header (12 columns, in order):
  `business_name,category,town,region,phone,website,online_ordering,call_volume_indicator,chain_or_independent,source_url,priority,pitch_angle`
- `outreach/*.md` — one email draft per prospect (`<slug>.md`; a few are `draft-<slug>.md`).
- `outreach/manifest.csv` — send queue. Header: `slug,business,email_draft_file,status(queued)`.
  `email_draft_file` is a filename relative to `outreach/`.
- `README.md` — thesis, territory, sourcing/verification doctrine, data caveats, legal & conduct rules.
- `OUTREACH.md` — sales kit (offer, scripts, objections, billing).
- `PLAYBOOK.md` — per-customer onboarding checklist.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md` — agent instruction files.
- Factory files: `GLOBAL_RULES.md`, `FACTORY_RULES.md`, `mission.md`.
- **Never guess a path.** Run `git ls-files` (or `ls`) before referencing a file.

## Commands
- Runtime available: `python3` (3.13 on the factory box). Use the standard library only
  unless a spec explicitly justifies a dependency.
- Validation: **none exists yet.** Until the validation-harness ticket lands, the
  minimum check before any PR is that both CSVs still parse with a consistent column count:
  `python3 -c "import csv;[print(f, {len(r) for r in csv.reader(open(f, newline=''))}) for f in ('prospects.csv','outreach/manifest.csv')]"`
  (each file must print a set containing exactly one number: 12 and 4).
- When a validation script is added, its exact command replaces the line above in this file.

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
