# PM-070 — GitHub

**Company:** GitHub  
**Category:** Conflicts  
**Source:** https://github.blog/news-insights/company-news/github-availability-report-october-2020/

## Incident Summary

During routine ZooKeeper reprovisioning, replacement hosts were added too quickly and elected a second leader, creating two distinct ZooKeeper clusters. A Kafka broker for the background-job system connected to the new cluster and elected itself controller, so two Kafka clusters served conflicting state to clients; ~10% of background-job writes failed over 2h32m.
