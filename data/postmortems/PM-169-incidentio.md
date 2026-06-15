# PM-169 — incident.io

**Company:** incident.io  
**Category:** Uncategorized  
**Source:** https://incident.io/blog/intermittent-downtime

## Incident Summary

A bad event (poison pill) in the async workers queue triggered unhandled panics that repeatedly crashed the app. This combined poorly with Heroku infrastructure, making it difficult to find the source of the problem. Applied mitigations that are generally interesting to people running web services, such as catching corner cases of Go panic recovery and splitting work by type/class to improve reliability.
