# PM-149 — GitHub

**Company:** GitHub  
**Category:** Uncategorized  
**Source:** https://github.blog/news-insights/company-news/github-availability-report-october-2024/

## Incident Summary

A database migration broke DNS resolution at one of GitHub's three sites, and recovery attempts cascaded to take down the rest of that site's DNS infrastructure. Repointing to a different site restored that site but broke cross-site connectivity from healthy sites; full recovery required deploying temporary DNS resolvers into the degraded site. Code search was 100% down for ~4 hours; total impact 19h12m.
