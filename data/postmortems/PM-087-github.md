# PM-087 — GitHub

**Company:** GitHub  
**Category:** Database  
**Source:** https://github.blog/2022-03-23-an-update-on-recent-service-disruptions/

## Incident Summary

Peak-hour load on the shared `mysql1` cluster repeatedly exhausted ProxySQL connections over a week, requiring four primary failovers plus an emergency index and proactive throttling of webhooks and Actions. Memory profiling turned on to debug performance later triggered another connection failure, requiring yet another failover.
