# PM-041 — rust-lang

**Company:** rust-lang  
**Category:** Config Errors  
**Source:** https://blog.rust-lang.org/inside-rust/2023/02/08/dns-outage-portmortem.html

## Incident Summary

On Wednesday, 2023-01-25 at 09:15 UTC, we deployed changes to the production infrastructure for crates.io. During the deployment, the DNS record for static.crates.io failed to resolve for an estimated time of 10-15 minutes. It was due to the fact that both certificates and DNS records were re-created during the downtime.
