# PM-068 — GitHub

**Company:** GitHub  
**Category:** Conflicts  
**Source:** https://github.blog/news-insights/the-library/downtime-last-saturday/

## Incident Summary

During an aggregation-switch ISSU upgrade, terminating an agent on one switch left the link up just long enough for the peer's MLAG failover to use the disruptive (rather than stateful) path, freezing the network for ~90 seconds. That spike caused fileserver Pacemaker/Heartbeat/DRBD pairs in different racks to exceed their heartbeats and STONITH each other, leaving many active/passive pairs with both nodes powered off; recovery required identifying the previously-active node from logs for each pair and took >5 hours.
