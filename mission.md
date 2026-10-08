# Mission: keep Cortese Digital's busy-line recovery sales pipeline accurate, safe to act on, and easy to work

Items marked **[ASSUMPTION]** were inferred by the factory setup agent from the
README, docs, data, and commit history on 2026-10-07. Stephen: correct or delete them.

## Context (from README.md)
Cortese Digital (owner-operator Stephen, Binghamton NY) sells a missed-call →
text-back / order-recovery service to independent restaurants: busy/no-answer
forwarding, a counter tablet, $0 upfront, 15% of recovered sales only. This repo
holds the lead list (`prospects.csv`), per-prospect email drafts (`outreach/`), the
send queue (`outreach/manifest.csv`), and the sales/onboarding docs.

## Goals
- Every lead row is verified from a cited public source and carries the fields
  Stephen needs to prioritize a call (phone, ordering setup, call-volume signal,
  independence, priority, pitch angle).
- **[ASSUMPTION]** The data is machine-checkable: consistent schema, controlled
  vocabularies for `priority` / `online_ordering` / `call_volume_indicator` /
  `chain_or_independent`, one phone format, and automated checks that catch
  mistakes before they reach a send queue.
- **[ASSUMPTION]** Nothing closed, disqualified (`priority=drop`), hijacked-site,
  or opted-out ever sits in the send queue, and no business is queued twice.
- **[ASSUMPTION]** Outreach state (drafted / queued / sent / replied / opted-out)
  is recorded in one structured place instead of commit messages and free-text headers.
- Docs (README counts, territory, offer naming) match the data actually in the repo.
- All outreach content stays honest and compliant per README "Legal & conduct note":
  STOP opt-out in every draft, no guaranteed numbers, vendor stats framed as directional.

## Non-goals (the factory may REJECT specs that require these)
- Sending email, calling, texting, or otherwise contacting any business, or
  automating sending/dialing (README forbids auto-dial; sending is a human act).
- Building the recovery product itself (telephony, tablet app, text-back, Stripe
  billing, 10DLC registration). **[ASSUMPTION]** that lives elsewhere, not in this repo.
- Scraping behind logins, buying lead lists, or collecting private/personal data.
- Inventing or "estimating" contact details, owner names, or revenue figures.
- **[ASSUMPTION]** A hosted CRM, web app, or database — CSV + Markdown in git stays the system of record.
- **[ASSUMPTION]** Bulk lead-research waves (new territories/verticals) as factory
  tickets — those need live web verification and human judgment; they stay manual/agent-assisted outside the factory.

## Current priorities
1. **[ASSUMPTION]** A minimal, stdlib-only validation harness for `prospects.csv`
   and `outreach/` + `outreach/manifest.csv` (the factory cannot iterate without it).
2. **[ASSUMPTION]** Fix the data/queue inconsistencies that harness exposes
   (e.g. a queued draft for a business the README lists as closed).
3. **[ASSUMPTION]** Structured outreach status (sent / opt-out tracking) so no one is double-sent or re-touched after STOP.
4. Bring README counts/territory/naming in line with the data.

## Definition of done (per issue)
- Visible validation command(s) in `GLOBAL_RULES.md` pass; holdout scenarios pass
  (validator session); no rule in `FACTORY_RULES.md` broken.
- PR open with what changed and the exact commands run; merged only by Stephen or a
  separate validator session — never by the builder. (No deploy step: this repo has no runtime.)
