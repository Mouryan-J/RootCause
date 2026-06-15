# PM-084 — GitHub

**Company:** GitHub  
**Category:** Database  
**Source:** https://github.blog/news-insights/the-library/github-availability-this-week/

## Incident Summary

A schema migration produced enough load that Percona Replication Manager failed the MySQL master over to a node with a cold InnoDB buffer pool, which then failed back. Disabling Pacemaker `maintenance-mode` the next day triggered a Pacemaker segfault that produced a partition; two simultaneous master elections occurred and the elected primary was the stale node, allowing 7 minutes of data drift in which 16 private repositories were briefly routed to the wrong owners.
