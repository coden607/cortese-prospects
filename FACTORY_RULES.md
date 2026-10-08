# Factory Rules — autonomous sessions only

Loaded ONLY in autonomous factory sessions (in addition to `GLOBAL_RULES.md`
and `mission.md`). Current autonomy level: **3 (human-in-the-loop)** — Stephen
approves every ticket plan and checks every result. Do not act as level 4/5
until Stephen raises the level in this file.

## Never
- **Never force-push** (`--force`, `--force-with-lease`, history rewrites on shared branches).
- **Never skip validation.** Run the full visible validation command in
  `GLOBAL_RULES.md` and iterate until it passes. Unvalidated work does not count.
- **Never weaken, delete, or bypass a check** to make it pass.
- **Never merge your own PR**, close your own ticket, or approve your own work.
  Merge decisions belong to the validator session or Stephen.
- **Never touch secrets or production config**: no credentials, tokens, `.env`
  files, Stripe/telephony/10DLC settings, GitHub Actions secrets, repo settings,
  or deploy configuration.
- Never change CI workflows (`.github/workflows/`) or the holdout scenarios
  without an explicit human-approved ticket that names that change.
- Never push to `main` directly.
- **Never contact a business.** No emails, calls, texts, form submissions, or
  social posts. Editing a draft or flipping a status column is allowed only when
  the ticket says so; *sending* is always a human action outside the factory.
- Never invent lead data (phones, emails, addresses, owners, review quotes) or
  claim a check/test passed that you did not run.
- Never add dependencies not justified in the spec.

## Hard stops — stop and escalate to Stephen
- **After 2 failed attempts on the same blocker**, stop. Post the blocker as a PR
  or issue comment (what you tried, exact error), set the issue to `blocked`, and halt.
- Any task that would require a "Never" action above.
- Any change that would delete rows from `prospects.csv`, delete outreach drafts,
  or alter opt-out / do-not-contact information.
- Ambiguity between a ticket and `mission.md` non-goals — reject or ask, don't improvise.

## Always
- Read `GLOBAL_RULES.md`, `mission.md`, and the ticket spec/slice before acting.
- One slice = one branch = one PR. Open the PR, describe what changed and exactly
  which commands you ran with their output, then STOP.
- Builder sessions never read holdout scenarios (they live outside this repo).
- Report results honestly, including partial failures.
