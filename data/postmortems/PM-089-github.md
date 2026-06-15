# PM-089 — GitHub

**Company:** GitHub  
**Category:** Database  
**Source:** https://github.blog/news-insights/company-news/addressing-githubs-recent-availability-issues-2/

## Incident Summary

Two popular client apps had been quietly increasing read traffic 10×, then a Saturday change shortened a user-settings cache TTL from 12h to 2h. On Monday's peak, the combined write amplification from cache rewrites plus read load overwhelmed the core auth/user-management database cluster, cascading through every service that depends on it (github.com, API, Actions, Git over HTTPS, Copilot, etc.).
