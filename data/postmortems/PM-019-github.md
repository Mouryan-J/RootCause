# PM-019 — GitHub

**Company:** GitHub  
**Category:** Config Errors  
**Source:** https://github.blog/news-insights/company-news/github-availability-report-august-2024/

## Incident Summary

A configuration change rolled out to GitHub.com databases broke the way hosts answered routing-service health-check pings, so the production read-only endpoint was marked unhealthy and inaccessible. With reads broken, the entire site was down for read operations for 36 minutes until the change was reverted.
