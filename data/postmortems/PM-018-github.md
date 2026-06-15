# PM-018 — GitHub

**Company:** GitHub  
**Category:** Config Errors  
**Source:** https://github.blog/news-insights/the-library/dns-outage-post-mortem/

## Incident Summary

A Puppet manifest bug restarted only the authoritative nameserver (not the caching one) after an IP change, causing query timeouts. The deploy run during incident response then rebuilt the zone file from an internal provisioning API call that itself depended on DNS, producing a corrupt zone with `NXDOMAIN` for many records. Memory exhaustion from spawned processes on the fileservers extended impact to 1h35m of partial downtime.
