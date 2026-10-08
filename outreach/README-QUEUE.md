# Send queues

- **Live send queue:** the dated files `outreach/queue-YYYY-MM-DD.txt`, one per send date.
  The format is one entry per line: `email | Business (Location) | source note | status note`.
  Lines starting with `#` are headers or comments. The first field can be a slug instead of
  an email while the email is still being found.
- **Legacy queue:** `outreach/manifest.csv`. It hasn't been updated since commit 30aa821
  (2026-10-06) and isn't sent from. Its rows are kept for history; don't delete or reorder them.
- **Do-not-contact:** `outreach/do_not_contact.csv` (`business,email,reason,added`).
  Any live queue entry that matches it by business name or email is a hard validation error.
  Only Stephen adds rows.

Check before sending: `python3 scripts/validate.py` (live queues dated today or later) or
`python3 scripts/validate.py --all-queues`.
