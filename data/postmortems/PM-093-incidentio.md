# PM-093 — incident.io

**Company:** incident.io  
**Category:** Database  
**Source:** https://status.incident.io/incidents/01JRDFKAGE07YYDY0KZR137BX3/write-up

## Incident Summary

After a Postgres 17 upgrade the weekend before, PGAudit was re-enabled based on staging testing. A routine migration to create an empty table and add an index triggered a pathological interaction with PGAudit: the extension hung while holding critical locks, ignored timeout signals, and blocked other DB operations across the dashboard, mobile app, Slack app, and API. The primary was restarted to break the deadlock (~2 minutes hard outage), then PGAudit was removed entirely.
