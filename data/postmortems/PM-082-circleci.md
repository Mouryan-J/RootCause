# PM-082 — CircleCI

**Company:** CircleCI  
**Category:** Database  
**Source:** https://status.circleci.com/incidents/8rklh3qqckp1

## Incident Summary

At peak Wednesday-afternoon load, the primary database backed up with queued operations to the point that it stopped catching up; rolling back recent changes had no isolated effect because the queue depth had already saturated the system, and a primary failover to kill queued ops only bought temporary headroom. After the runnable-queue was drained, builds were stuck in the prior queue stage; manually promoting them flooded the next queue, and the build-scheduler's failure-mode throttles fired on what were actually normal conditions and backed off precisely when more throughput was needed. CircleCI rebuilt tooling on the fly to clear a 17-hour backlog.
