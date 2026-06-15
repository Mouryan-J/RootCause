# PM-180 — Launchdarkly

**Company:** Launchdarkly  
**Category:** Uncategorized  
**Source:** https://launchdarkly.com/blog/what-happened-what-we-learned-and-how-were-improving/

## Incident Summary

The AWS us-east-1 outage degraded EC2/Lambda/DynamoDB/Route 53, leaving Launchdarkly's US web app, API, and client-side streaming SDKs unable to autoscale and dropping events. After AWS recovered, an internal change meant to shed load reverted flag-delivery to a legacy routing path with cold caches; SDKs hammered the streaming service with retries, the load balancer became unresponsive, and EC2 provisioning issues prevented scale-out, taking server-side streaming globally to ~99% errors and keeping US streaming down for another ~12 hours.
