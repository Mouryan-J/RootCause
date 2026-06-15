# PM-056 — Amazon

**Company:** Amazon  
**Category:** Hardware/Power Failures  
**Source:** https://aws.amazon.com/message/56489/

## Incident Summary

A bug in third-party datacenter control system code caused excessive interactions during a control-host failover, making the cooling control system unresponsive. Most of the datacenter correctly failed cooling into "max cooling" mode, but in a small portion the cooling units shut down instead, and the operator-initiated "purge" mode also failed because the PLCs controlling the air handlers had become unresponsive too. EC2 servers in one Tokyo AZ overheated and powered off; customers using ALB + AWS WAF or sticky sessions saw cross-AZ impact despite running multi-AZ.
