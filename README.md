# cortese-prospects

Sales pipeline for **Continuity OS** — a missed-call → text-back / order-recovery service for independent restaurants. Busy-line forwarding, counter tablet, **$0 upfront, 15% of recovered sales only**.

Owner-operator: Stephen (Binghamton, NY). Territory: Broome County core + the I-81/I-86/I-88 corridor (Owego → Cortland → Ithaca → Syracuse → Utica → Elmira-Corning) + Northern PA fringe (Sayre/Athens, Scranton, Wilkes-Barre).

## The thesis

Independent restaurants lose real money one ringing phone at a time. At Friday dinner rush the line is busy, the caller doesn't leave a voicemail — they dial the next pizzeria on the list. The owner never sees the loss, so they never budget to fix it. Our wedge: **zero risk** (no upfront cost, fee only on provably recovered orders) + **a tablet on their counter showing the recovered money in real time.** The monthly recovered-revenue report turns "a service I pay for" into "money I'd be stupid to turn off."

## What's in this repo

- **`prospects.csv`** — 54 verified leads across 16 towns / 12 counties / 2 states. Columns include category, call-volume signal, chain vs. independent, source URL, priority (A = phone-first high-volume independent, B = good fit, C = corporate/online-first/low fit), and a one-line pitch angle.
- **`OUTREACH.md`** — the sales kit: offer, cold-call script, the busy-signal demo tactic, objection handling, monthly billing mechanic.
- **`PLAYBOOK.md`** — the per-customer replication checklist (deploy → register → forward-test → handoff → pilot → report → go-live) plus churn-retention and land-and-expand mechanics.

## Sourcing & verification method

Every lead was compiled from public sources during October 2026 research passes:

1. Business's own website or official Facebook page (preferred)
2. Official tourism-bureau directories (visitbinghamton.org / Broome County CVB, visitbradfordcounty.com)
3. Reputable public listings and local press (Ithaca Times dining guide, syracuse.com / pressconnects, Tripadvisor/Yelp entity pages)

**Verification doctrine:** every row carries a `source_url`. Phone numbers were transcribed ONLY from the business's own site/FB or a reputable listing — zero invented digits. Rows that couldn't be verified were dropped, not guessed (that's why some famous names are absent). Independents vs. chains are marked; regional mini-chains (2+ locations: Nirchi's, Spiedie & Rib Pit, Tully's, Pavone's, Pontillo's, Atlas, Grotto-PA, O'Scugnizzo) are flagged as chain-pilot candidates.

### Known data caveats (verify on first call — costs 10 seconds)

- **Rossi's Pizza (Endicott):** website shows (607) 754-4567; an older FB listing shows 607-777-1313. Website wins; confirm on pickup.
- **Nando's (Endwell):** own site shows (607) 754-5411; the CVB directory shows (607) 798-0439. Own-site wins.
- **Fuji San (Vestal):** CVB lists 100 Rano Blvd / (607) 261-3333; an older listing shows Vestal Pkwy E. Likely moved — confirm address.
- **Lupo's Char-Pit:** the surviving location is 2710 E Main St, Endicott. Do NOT confuse with Lupo's S&S Char-Pit (6 W State St, Binghamton — **closed 2023**) or Sharkey's (Glenwood Ave — **closed 2020**). Both closures confirmed via pressconnects / WNBF / syracuse.com during research.
- **Copper Top Tavern (Vestal):** multi-location status (2+ sites) and phone sourced from secondary listings; confirm on first call.
- **China Garden (Endicott):** phone (607) 786-2165 per Broome County CVB; a Nextdoor listing corroborates the same digits.
- **HK Takeout (Syracuse):** own site shows 315-428-0395; some third-party listings show (315) 350-3246. Own-site wins.
- **Rome NY gap:** no Rome lead survived verification (the surfaced candidate, Luigi's II, is closed). Rome is served as part of the Utica-Rome region via the four Utica leads; add Rome rows in a future pass.
- **Athens PA:** covered jointly with twin-city Sayre (one lead). Expand in a future pass.
- Priorities and call-volume indicators are desk-research estimates — re-rate after the first conversation.

## Legal & conduct note

- This list uses **public business information only** (published phone numbers, addresses, websites). No private data, no scraping behind logins.
- Outreach hours: **2–4 PM, owner-preference permitting. Never lunch or dinner rush.** One busy-signal demo call per prospect per Friday (that's research, not harassment — do not auto-dial or spoof).
- **Honor opt-outs immediately and permanently.** "Stop calling" means stop — mark the CRM and never re-touch (a 90-day cool-down applies only to non-answers, never to explicit opt-outs).
- Texting to consumers runs through registered 10DLC A2P campaigns (see PLAYBOOK.md §2). Every message includes STOP opt-out handling. TCPA compliance is a feature, not paperwork.
- Honesty rule from the founder down: stats cited in the original demo deck (missed-call → lost-customer percentages, average order values) come from **vendor-funded industry studies**. Present them as directional, never as guarantees. The only numbers we ever promise are the ones on the customer's own tablet log.
- Don't oversell. "$0 upfront, 15% of what we recover, cancel anytime" is the whole pitch — anything louder is a lie waiting to be discovered.

## Changelog

- **2026-10-06** — Initial pipeline: 54 leads + outreach kit + replication playbook. Research pass 1.
