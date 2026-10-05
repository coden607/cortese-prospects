# PLAYBOOK.md — Per-customer replication checklist

Every new restaurant goes through the same pipeline. Total time from signed pilot to go-live: **one afternoon of work + a 2-week pilot**.

## 0. Pre-flight (before you touch their systems)
- [ ] Confirm decision-maker on site (owner or GM with authority to approve)
- [ ] Confirm phone setup: how many lines, who the carrier is, whether they have call forwarding feature codes
- [ ] Confirm they own their phone number (not corporate-manged PBX) — if corporate, get the ops contact (see OUTREACH objection handling)
- [ ] Pick the pilot start date; add to tracker sheet

## 1. Deploy clone (~1 hour)
- [ ] Clone the Continuity OS template into a new tenant: `{restaurant-slug}.continuity-os` config
- [ ] Load their menu + logo into the text-back template; test-render on your own phone
- [ ] Set the recovery offer text: apology + menu link + "reply to get a call back" option
- [ ] Provision the counter tablet (or configure email-to-printer if they prefer their existing POS printer)
- [ ] Create their Stripe customer record + draft the 15%-of-recovered invoice template
- [ ] Set quiet hours (never text customers after 9 PM), opt-out keyword (STOP), and owner notification preferences

## 2. Carrier texting registration
- [ ] Register the texting number for 10DLC A2P compliance (brand + campaign registration) — this is what keeps texts from being filtered as spam
- [ ] Use the restaurant's existing number via hosted texting if the carrier supports it; otherwise provision a local number in their area code that shows their name as the sender profile
- [ ] Verify registration approval BEFORE go-live; unregistered campaigns get throttled/blocked
- [ ] Test-send to three test numbers (your phone, owner's phone, one staff phone) from the registered campaign

## 3. Busy-forward test on their real lines
- [ ] Walk the owner through enabling busy/no-answer forwarding on their actual line (`*90`-style codes or carrier portal) — set busy-forward to our number
- [ ] Call line 1 while it's in use; confirm the text-back fires within 30 seconds
- [ ] Call both lines simultaneously during a quiet period (simulate); confirm both recoveries land on the tablet
- [ ] Have the owner place a fake order from the text link; confirm the ticket prints/appears at the counter
- [ ] Give the owner a laminated card: "To pause service: [code]. To resume: [code]." They must always have an escape hatch

## 4. Tablet handoff with staff passcode
- [ ] Physical install: counter position with power, brightness locked, staff passcode set (owner picks it — write it on the handoff sheet)
- [ ] Train 2+ staff members for 10 minutes each: view ticket → tap approve → kitchen. That's the entire UI.
- [ ] Staff demo: simulate two simultaneous recoveries; show that approving one and calling back the other both work
- [ ] Post the one-page staff cheat-sheet next to the tablet
- [ ] Owner gets the dashboard link + the weekly auto-email summary

## 5. Two-week pilot
- [ ] Service live, fees waived during pilot — position it as "let's count your misses together"
- [ ] **Week 1:** daily check-in text to owner ("3 recoveries yesterday, $87"). Catch and fix anything within 24h.
- [ ] **Week 2:** check-ins every other day; collect any disputed orders and resolve immediately
- [ ] End of pilot: generate the recovered-revenue report from the tablet log

## 6. Owner report review (the closing meeting — 20 minutes, on site or call)
- [ ] Show: total missed calls, recoveries, recovered revenue, their cut, your 15%
- [ ] Show the raw log (timestamps + numbers) — invite them to spot-check any order against their own records
- [ ] Ask the magic question: *"Do you want to keep this running, or should we turn it off?"* (Silence sells. They never say turn it off if the report is real.)
- [ ] Sign the ongoing agreement: month-to-month, either party cancels with 30 days' notice, no termination fee

## 7. Go-live
- [ ] Flip from pilot mode to billing mode; schedule the first invoice for the 1st
- [ ] Calendar the first 90-day review now (don't wait for them to call you)
- [ ] Ask for two referrals: *"Which two restaurant-owner friends would also want their Friday 6 PM calls back?"* — hand them a card

---

## Churn-retention mechanics

- **The monthly recovered-$ report IS the renewal reason.** Every invoice ships with a one-pager: orders recovered, revenue recovered, fee, net-to-owner. A restaurant that sees "$2,800 recovered last month" never cancels; cancellation feels like choosing to lose the money again. Never send a bare invoice.
- **Quarterly review call (15 min):** trending chart of recoveries, peak miss hours (they adjust staffing), and any new lines/locations.
- **First-90-days red flag watch:** if week-4 recoveries drop below pilot average, visit in person. Churn is almost always a training/usage problem (staff stopped approving tickets), not a value problem. Fix the behavior before they decide.
- **Win-back file:** cancelled accounts get a friendly check-in at 60 days with their old recovered-revenue report attached. One nudge only.
- **Annual loyalty:** after 12 months, lock fee rate for the next 12 with a one-page renewal. No discounting — the report is the value.

## Land-and-expand

- **Menu-link texting:** recovered customers get a reorder link; offer the owner SMS marketing blasts to their own opted-in recovery list (slow Tuesday push) as an add-on.
- **Catering follow-ups:** every recovered order tagged "large order" triggers a catering follow-up template — turns one saved dinner into a booked party.
- **Second location:** multi-unit successes (Nirchi's, Pavone's, Spiedie & Rib Pit, Tully's, Pontillo's, Grotto, Atlas) get a group rate conversation at location #2: pilot results from store 1 are the pitch for store 2. One dashboard, one invoice, per-location reports.
- **Seasonal rush tuning:** grad weekends, Spiedie Fest, State Fair move-ins — pre-schedule capacity checks before known high-volume weekends.
