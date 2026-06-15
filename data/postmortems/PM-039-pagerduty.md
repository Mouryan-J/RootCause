# PM-039 — PagerDuty

**Company:** PagerDuty  
**Category:** Config Errors  
**Source:** https://status.pagerduty.com/incidents/vbp7ht2647l8

## Incident Summary

On December 15th, 2021 at 00:17 UTC, we deployed a DNS configuration change in PagerDuty’s infrastructure that impacted our container orchestration cluster. The change contained a defect, that we did not detect in our testing environments, which immediately caused all services running in the container orchestration cluster to be unable to resolve DNS.
