# PM-085 — GitHub

**Company:** GitHub  
**Category:** Database  
**Source:** https://github.blog/news-insights/company-news/february-service-disruptions-post-incident-analysis/

## Incident Summary

The `mysql1` cluster experienced four ProxySQL meltdowns over nine days: an analytics query hitting the master instead of replicas, a planned promotion that recreated the failure, and then two load-driven incidents revealing that systemd had silently capped `LimitNOFILE` from 1,073,741,824 to 65,536 because of a kernel-level limit of 1,048,576. Total impact was 8h14m across the four incidents.
