# PM-215 — Stripe

**Company:** Stripe  
**Category:** Uncategorized  
**Source:** https://support.stripe.com/questions/outage-postmortem-2015-10-08-utc

## Incident Summary

Manual operations are regularly executed on production databases. A manual operation was done incorrectly (missing dependency), causing the Stripe API to go down for 90 minutes.
