# PM-171 — incident.io

**Company:** incident.io  
**Category:** Uncategorized  
**Source:** https://incident.io/blog/service-disruption-october-20th-2025

## Incident Summary

During the AWS us-east-1 outage, incident.io's Google-Cloud-hosted platform mostly held but third-party AWS dependencies cascaded into a complex multi-team response: their telecom provider's outage backed up the on-call notification queue (~30× normal load), their deploy pipeline was wedged because their builder transitively pulled `golang:1.24.9-alpine` from Docker Hub (which runs on AWS), and Postgres dead tuples in the escalation-acquisition index turned scaling up workers into a net throughput regression. A traffic-management feature flag also failed to apply globally because of a recent "top 10 orgs by volume" usability tweak.
