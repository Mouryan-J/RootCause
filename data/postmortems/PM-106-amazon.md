# PM-106 — Amazon

**Company:** Amazon  
**Category:** Uncategorized  
**Source:** https://aws.amazon.com/message/073024/

## Incident Summary

A Kinesis cell newly migrated to a new architecture had an unusually high number of very low-throughput shards. The cell management system distributed the shards unevenly, so a few hosts ended up handling huge numbers of shards and produced abnormally large status messages. The system misinterpreted slow status messages as host failures, kicked off a redistribution storm, and overloaded the secure-connection provisioning subsystem. CloudWatch Logs, S3 event notifications, Firehose, ECS, Lambda, Redshift, MWAA, and Glue all degraded for ~7 hours.
