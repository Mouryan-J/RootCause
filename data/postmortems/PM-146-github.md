# PM-146 — GitHub

**Company:** GitHub  
**Category:** Uncategorized  
**Source:** https://github.blog/news-insights/the-library/network-problems-last-friday/

## Incident Summary

A misconfigured "partial link failure" detection feature on access switches caused redundant links to be wrongly disabled during testing, producing 18 minutes of hard downtime. The underlying day-long degradation turned out to be a vendor bug that prevented the new aggregation switches from learning a large fraction of MAC addresses, so most traffic was being flooded out every port and saturating uplinks.
