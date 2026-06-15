# PM-010 — Cloudflare

**Company:** Cloudflare  
**Category:** Config Errors  
**Source:** https://blog.cloudflare.com/1-1-1-1-lookup-failures-on-october-4th-2023/

## Incident Summary

On 4 October 2023, Cloudflare experienced DNS resolution problems starting at 07:00 UTC and ending at 11:00 UTC. Some users of 1.1.1.1 or products like WARP, Zero Trust, or third party DNS resolvers which use 1.1.1.1 may have received SERVFAIL DNS responses to valid queries. We’re very sorry for this outage. This outage was an internal software error and not the result of an attack. In this blog, we’re going to talk about what the failure was, why it occurred, and what we’re doing to make sure this doesn’t happen again.
