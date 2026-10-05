# PLAYBOOK — Replicating the Cortese Engine Per Customer

*Cortese Restaurant (Binghamton) is the reference build. Every new customer = one cloned deploy + config. Target setup time: under 2 hours of your labor.*

## Per-customer checklist
1. **Deploy clone** (~30 min): copy the app, rename, set env (customer name, two answering numbers, staff passcode). Vercel + Railway as per current stack.
2. **Texting registration** ($19.50 once per customer, carrier-required): register the two answering numbers for A2P texting in the customer's own Twilio/texting account. Numbers cost ~$1.15/mo each — YOUR cost, covered by your share.
3. **Busy-forwarding** (15 min, WITH the owner): one setting per line with their phone company: *call forward when busy* → answering number. Test that ONLY busy calls forward, and that caller ID passes through. Reversible by them any time.
4. **Tablet handoff**: any browser tablet at the counter, signed in with staff passcode. 10-minute staff training: Confirm / Can't take it / Call guest. Staff can kill any order — nothing is promised without a human tap.
5. **2-week pilot**: measure busy calls, text-backs, confirmed orders, recovered revenue. Pilot report to owner = the sales document.
6. **Go-live + monthly loop**: 1st-of-month report + Stripe link (see OUTREACH.md). 

## Churn reality (you named it — here's the defense)
Customers leave when they find something better, relocate, or close. You can't contract-lock them (and shouldn't — the no-contract offer IS the pitch). Your retention mechanics:
- **The monthly recovered-$ report** is the renewal pitch. As long as it shows money they couldn't otherwise get, leaving = cutting off their own revenue.
- **Land-and-expand**: after go-live, add (a) menu-link texting after the text-back, (b) catering/large-order follow-ups, (c) location #2, #3 (Nirchi's, Lupo's, Spiedie & Rib Pit are built for this).
- **The tablet habit**: once staff tap Confirm all night, the workflow IS the moat. Switching away means retraining staff — that's friction in YOUR favor.
- **Exit gracefully anyway**: a customer who leaves happy refers. Every departure gets a "turn it back on any time, here's your number" note.

## Unit economics (per customer)
- Your costs: ~$2.30 numbers + $1.50 registration + $5 hosting + per-message pennies ≈ **$9–52/mo** depending on volume.
- Your revenue: 15% of recovered orders. At 100 busy calls/mo and conservative 25–35% text-back→order conversion at a $38 avg ticket: roughly **$285–800/mo** per customer.
- **10 active customers ≈ $3K–8K/mo gross** before your tiny costs. That's the business.

## Expansion verticals (later — same engine, different words)
- **Auto dealerships**: busy service lanes → appointment recovery (you know Cortese Chrysler's world).
- **HVAC/plumbing**: missed call = $300–800 job. Same 15% or flat per-booked-job fee.
- **Salons/barbershops**: booking-line misses.
The restaurant playbook stays the beachhead — food orders are the highest-frequency proof.
